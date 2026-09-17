package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const version = "0.1.0"
const protocolVersion = 1
const maxBody = 64 * 1024

type NetworkConfig struct {
	URL       string `json:"url"`
	PublicKey string `json:"public_key"`
	Invite    string `json:"invite"`
}
type Job struct {
	Protocol    int       `json:"protocol"`
	Model       string    `json:"model"`
	ID          string    `json:"id"`
	NodeID      string    `json:"node_id"`
	Round       int       `json:"round"`
	BaseVersion int       `json:"base_version"`
	BaseHash    string    `json:"base_hash"`
	Weights     []float64 `json:"weights"`
	Seed        uint64    `json:"seed"`
	Steps       int       `json:"steps"`
	Issued      int64     `json:"issued"`
	Expires     int64     `json:"expires"`
}
type Envelope struct {
	Payload   string `json:"payload"`
	Signature string `json:"signature"`
}
type JoinRequest struct {
	Invite string `json:"invite"`
	OS     string `json:"os"`
	Arch   string `json:"arch"`
}
type JoinResponse struct {
	NodeID string `json:"node_id"`
	Token  string `json:"token"`
}
type PollRequest struct {
	Ready bool `json:"ready"`
}
type PollResponse struct {
	State        string    `json:"state"`
	ModelVersion int       `json:"model_version"`
	ActiveRound  int       `json:"active_round"`
	Job          *Envelope `json:"job,omitempty"`
}
type Result struct {
	JobID   string    `json:"job_id"`
	Weights []float64 `json:"weights"`
}

func randomToken(n int) string {
	b := make([]byte, n)
	if _, e := rand.Read(b); e != nil {
		panic(e)
	}
	return base64.RawURLEncoding.EncodeToString(b)
}
func secureEqual(a, b string) bool {
	ha := sha256.Sum256([]byte(a))
	hb := sha256.Sum256([]byte(b))
	return subtle.ConstantTimeCompare(ha[:], hb[:]) == 1
}
func tokenHash(s string) string                { h := sha256.Sum256([]byte(s)); return hex.EncodeToString(h[:]) }
func publicKeyText(k ed25519.PublicKey) string { return base64.RawURLEncoding.EncodeToString(k) }
func signJob(k ed25519.PrivateKey, j Job) (Envelope, error) {
	b, e := json.Marshal(j)
	if e != nil {
		return Envelope{}, e
	}
	return Envelope{base64.RawURLEncoding.EncodeToString(b), base64.RawURLEncoding.EncodeToString(ed25519.Sign(k, b))}, nil
}
func verifyJob(e Envelope, key, nodeID string, now time.Time) (Job, error) {
	var j Job
	pk, err := base64.RawURLEncoding.DecodeString(key)
	if err != nil || len(pk) != 32 {
		return j, errors.New("invalid network signing key")
	}
	b, err := base64.RawURLEncoding.DecodeString(e.Payload)
	if err != nil || len(b) > maxBody {
		return j, errors.New("invalid signed payload")
	}
	sig, err := base64.RawURLEncoding.DecodeString(e.Signature)
	if err != nil || !ed25519.Verify(pk, b, sig) {
		return j, errors.New("task signature rejected")
	}
	if err = json.Unmarshal(b, &j); err != nil {
		return j, err
	}
	if j.Protocol != protocolVersion || j.Model != modelID || j.NodeID != nodeID || j.ID == "" || j.Round < 1 || j.BaseVersion < 0 || !validWeights(j.Weights) || j.BaseHash != hashWeights(j.Weights) || j.Seed == 0 || j.Steps < 1 || j.Steps > maxSteps {
		return j, errors.New("task outside approved workload")
	}
	if now.Unix() < j.Issued-30 || now.Unix() >= j.Expires || j.Expires-j.Issued > 300 || j.Expires <= j.Issued {
		return j, errors.New("task expired or invalid time window")
	}
	return j, nil
}
func decodeConfig(text string) (NetworkConfig, error) {
	var c NetworkConfig
	b, e := base64.RawURLEncoding.DecodeString(strings.TrimSpace(text))
	if e != nil {
		return c, errors.New("invalid connection code")
	}
	if len(b) > 4096 {
		return c, errors.New("connection code too large")
	}
	if e = json.Unmarshal(b, &c); e != nil {
		return c, e
	}
	c.URL = strings.TrimRight(c.URL, "/")
	u, e := url.Parse(c.URL)
	if e != nil || u.Host == "" || u.User != nil || u.RawQuery != "" || u.Fragment != "" || (u.Path != "" && u.Path != "/") {
		return c, errors.New("network URL must be an HTTPS origin")
	}
	ip := net.ParseIP(u.Hostname())
	local := u.Hostname() == "localhost" || (ip != nil && ip.IsLoopback())
	if u.Scheme != "https" && !(u.Scheme == "http" && local) {
		return c, errors.New("HTTPS required; HTTP allowed only on loopback for local tests")
	}
	pk, e := base64.RawURLEncoding.DecodeString(c.PublicKey)
	if e != nil || len(pk) != 32 || len(c.Invite) < 16 || len(c.Invite) > 128 {
		return c, errors.New("invalid pinned network key or invite")
	}
	return c, nil
}
func encodeConfig(c NetworkConfig) string {
	b, _ := json.Marshal(c)
	return base64.RawURLEncoding.EncodeToString(b)
}
func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
func apiError(w http.ResponseWriter, code int, s string) {
	writeJSON(w, code, map[string]string{"error": s})
}
func readJSON(w http.ResponseWriter, r *http.Request, v any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBody)
	d := json.NewDecoder(r.Body)
	d.DisallowUnknownFields()
	if e := d.Decode(v); e != nil {
		return e
	}
	var extra any
	if e := d.Decode(&extra); e != io.EOF {
		return errors.New("only one JSON object is allowed")
	}
	return nil
}
func postJSON(client *http.Client, ctxURL string, token string, in, out any) error {
	b, e := json.Marshal(in)
	if e != nil {
		return e
	}
	r, e := http.NewRequest("POST", ctxURL, strings.NewReader(string(b)))
	if e != nil {
		return e
	}
	r.Header.Set("Content-Type", "application/json")
	if token != "" {
		r.Header.Set("Authorization", "Bearer "+token)
	}
	res, e := client.Do(r)
	if e != nil {
		return e
	}
	defer res.Body.Close()
	b, e = io.ReadAll(io.LimitReader(res.Body, maxBody+1))
	if e != nil {
		return e
	}
	if len(b) > maxBody {
		return errors.New("response too large")
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		var m map[string]any
		_ = json.Unmarshal(b, &m)
		return fmt.Errorf("network returned %d: %v", res.StatusCode, m["error"])
	}
	if out != nil {
		return json.Unmarshal(b, out)
	}
	return nil
}
func newHTTPClient() *http.Client {
	return &http.Client{Timeout: 5 * time.Second, CheckRedirect: func(*http.Request, []*http.Request) error { return errors.New("redirects are not allowed") }}
}
func atomicJSON(path string, v any) error {
	b, e := json.MarshalIndent(v, "", "  ")
	if e != nil {
		return e
	}
	return atomicBytes(path, b)
}
func atomicBytes(path string, b []byte) error {
	if e := os.MkdirAll(filepath.Dir(path), 0700); e != nil {
		return e
	}
	f, e := os.CreateTemp(filepath.Dir(path), ".tmp-*")
	if e != nil {
		return e
	}
	name := f.Name()
	defer os.Remove(name)
	if e = f.Chmod(0600); e == nil {
		_, e = f.Write(b)
	}
	if e == nil {
		e = f.Sync()
	}
	ce := f.Close()
	if e == nil {
		e = ce
	}
	if e != nil {
		return e
	}
	// Go's os.Rename uses replace-existing semantics on supported Windows builds.
	return os.Rename(name, path)
}
func secureLocal(next http.Handler, host, token string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		securityHeaders(w)
		if r.Host != host {
			apiError(w, 403, "unrecognized local host")
			return
		}
		origin := r.Header.Get("Origin")
		if origin != "" && origin != "http://"+host {
			apiError(w, 403, "cross-origin access denied")
			return
		}
		if strings.HasPrefix(r.URL.Path, "/api/") && !secureEqual(r.Header.Get("X-Session-Token"), token) {
			apiError(w, 401, "local session token required")
			return
		}
		next.ServeHTTP(w, r)
	})
}
func securityHeaders(w http.ResponseWriter) {
	w.Header().Set("X-Content-Type-Options", "nosniff")
	w.Header().Set("X-Frame-Options", "DENY")
	w.Header().Set("Referrer-Policy", "no-referrer")
	w.Header().Set("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
}
