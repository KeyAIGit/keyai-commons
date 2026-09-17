package main

// The optional Internet operator endpoint accepts four fixed, signed actions.
// It is not a remote shell. The private operator key never leaves its owner.
import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const operatorDomain = "keyai-commons/operator/v1\x00"

type OperatorCommand struct {
	Protocol int    `json:"protocol"`
	Action   string `json:"action"`
	Audience string `json:"audience"`
	Instance string `json:"instance"`
	Nonce    string `json:"nonce"`
	Issued   int64  `json:"issued"`
	Expires  int64  `json:"expires"`
	Steps    int    `json:"steps"`
	Nodes    int    `json:"nodes"`
	Seconds  int    `json:"seconds"`
}
type OperatorInfo struct {
	PublicKey string `json:"operator_public_key"`
	Instance  string `json:"instance"`
}
type CoordinatorOptions struct {
	OperatorKey string
	Persistence string
}

func validPublicKey(s string) bool {
	b, e := base64.RawURLEncoding.DecodeString(s)
	return e == nil && len(b) == ed25519.PublicKeySize
}
func signOperator(key ed25519.PrivateKey, q OperatorCommand) (Envelope, error) {
	b, e := json.Marshal(q)
	if e != nil {
		return Envelope{}, e
	}
	return Envelope{base64.RawURLEncoding.EncodeToString(b), base64.RawURLEncoding.EncodeToString(ed25519.Sign(key, append([]byte(operatorDomain), b...)))}, nil
}
func verifyOperator(env Envelope, key, origin, instance string, now time.Time) (OperatorCommand, error) {
	var q OperatorCommand
	pk, e := base64.RawURLEncoding.DecodeString(key)
	if e != nil || len(pk) != 32 {
		return q, errors.New("remote operator control is disabled")
	}
	b, e := base64.RawURLEncoding.DecodeString(env.Payload)
	if e != nil || len(b) > 4096 {
		return q, errors.New("invalid command payload")
	}
	sig, e := base64.RawURLEncoding.DecodeString(env.Signature)
	if e != nil || !ed25519.Verify(pk, append([]byte(operatorDomain), b...), sig) {
		return q, errors.New("operator signature rejected")
	}
	d := json.NewDecoder(strings.NewReader(string(b)))
	d.DisallowUnknownFields()
	if e = d.Decode(&q); e != nil {
		return q, errors.New("invalid command shape")
	}
	if q.Protocol != 1 || q.Audience != origin || q.Instance != instance || len(q.Nonce) < 24 || len(q.Nonce) > 128 {
		return q, errors.New("command audience, instance or nonce rejected")
	}
	if now.Unix() < q.Issued-5 || now.Unix() >= q.Expires || q.Expires <= q.Issued || q.Expires-q.Issued > 60 {
		return q, errors.New("command expired or invalid lifetime")
	}
	switch q.Action {
	case "start", "stop", "finalize", "enrollment_open", "enrollment_close":
	default:
		return q, errors.New("unsupported operator action")
	}
	if q.Action != "start" && (q.Steps != 0 || q.Nodes != 0 || q.Seconds != 0) {
		return q, errors.New("unexpected action parameters")
	}
	return q, nil
}
func (c *Coordinator) remoteCommand(w http.ResponseWriter, r *http.Request) {
	if c.operatorKey == "" {
		apiError(w, 404, "remote operator control is disabled")
		return
	}
	var env Envelope
	if readJSON(w, r, &env) != nil {
		apiError(w, 400, "invalid signed envelope")
		return
	}
	q, e := verifyOperator(env, c.operatorKey, c.config.URL, c.instance, time.Now())
	if e != nil {
		apiError(w, 403, e.Error())
		return
	}
	c.mu.Lock()
	for n, expiry := range c.replays {
		if expiry < time.Now().Unix() {
			delete(c.replays, n)
		}
	}
	if _, ok := c.replays[q.Nonce]; ok {
		c.mu.Unlock()
		apiError(w, 409, "operator command already used")
		return
	}
	if len(c.replays) >= 512 {
		c.mu.Unlock()
		apiError(w, 429, "command capacity reached")
		return
	}
	c.replays[q.Nonce] = q.Expires
	switch q.Action {
	case "start":
		e = c.startRoundLocked(q.Steps, q.Nodes, q.Seconds)
	case "stop":
		c.active = nil
	case "finalize":
		e = c.finalizeLocked()
	case "enrollment_open":
		c.publicEnrollment = true
		c.enrollmentClosed = false
	case "enrollment_close":
		c.publicEnrollment = false
		c.enrollmentClosed = true
	}
	c.mu.Unlock()
	if e != nil {
		apiError(w, 409, e.Error())
		return
	}
	writeJSON(w, 200, map[string]any{"ok": true, "action": q.Action, "instance": c.instance})
}
func operatorMain(args []string) error {
	if len(args) == 0 {
		return errors.New("operator init|status|open|close|start|stop|finalize --url HTTPS_ORIGIN [--data DIR]")
	}
	action := args[0]
	fs := flag.NewFlagSet("operator "+action, flag.ContinueOnError)
	dir := fs.String("data", defaultDir("operator"), "private operator key directory")
	url := fs.String("url", "", "coordinator HTTPS origin")
	steps := fs.Int("steps", 800, "training steps (10..1200)")
	nodes := fs.Int("nodes", 1, "target participants (1..32)")
	seconds := fs.Int("seconds", 120, "round deadline (30..240 seconds)")
	if e := fs.Parse(args[1:]); e != nil {
		return e
	}
	path := filepath.Join(*dir, "operator-key-private.json")
	if action == "init" {
		if _, e := os.Stat(path); e == nil {
			return errors.New("operator key already exists; refusing to overwrite")
		}
		_, key, e := ed25519.GenerateKey(rand.Reader)
		if e != nil {
			return e
		}
		if e = atomicJSON(path, map[string]string{"private_key": base64.RawURLEncoding.EncodeToString(key)}); e != nil {
			return e
		}
		fmt.Println("OPERATOR_PUBLIC_KEY=" + publicKeyText(key.Public().(ed25519.PublicKey)))
		fmt.Println("Private key saved locally. Back it up privately; never upload it to GitHub.")
		return nil
	}
	origin, e := checkedOrigin(*url)
	if e != nil {
		return e
	}
	if action == "status" {
		var s map[string]any
		if e = getJSON(newHTTPClient(), origin+"/v1/status", &s); e != nil {
			return e
		}
		b, _ := json.MarshalIndent(s, "", "  ")
		fmt.Println(string(b))
		return nil
	}
	var k struct {
		PrivateKey string `json:"private_key"`
	}
	b, e := os.ReadFile(path)
	if e != nil {
		return errors.New("operator key unavailable; run operator init first")
	}
	if e = json.Unmarshal(b, &k); e != nil {
		return e
	}
	key, e := base64.RawURLEncoding.DecodeString(k.PrivateKey)
	if e != nil || len(key) != 64 {
		return errors.New("invalid operator key")
	}
	var info OperatorInfo
	if e = getJSON(newHTTPClient(), origin+"/v1/info", &info); e != nil {
		return e
	}
	if info.PublicKey != publicKeyText(ed25519.PrivateKey(key).Public().(ed25519.PublicKey)) {
		return errors.New("server does not trust this operator key")
	}
	if action == "open" {
		action = "enrollment_open"
	}
	if action == "close" {
		action = "enrollment_close"
	}
	q := OperatorCommand{Protocol: 1, Action: action, Audience: origin, Instance: info.Instance, Nonce: randomToken(24), Issued: time.Now().Unix(), Expires: time.Now().Add(45 * time.Second).Unix()}
	if action == "start" {
		q.Steps = *steps
		q.Nodes = *nodes
		q.Seconds = *seconds
	}
	if _, e = verifyOperatorMust(q, ed25519.PrivateKey(key)); e != nil {
		return e
	}
	env, e := signOperator(ed25519.PrivateKey(key), q)
	if e != nil {
		return e
	}
	var result map[string]any
	if e = postJSON(newHTTPClient(), origin+"/v1/operator", "", env, &result); e != nil {
		return e
	}
	b, _ = json.MarshalIndent(result, "", "  ")
	fmt.Println(string(b))
	return nil
}
func verifyOperatorMust(q OperatorCommand, key ed25519.PrivateKey) (OperatorCommand, error) {
	env, e := signOperator(key, q)
	if e != nil {
		return q, e
	}
	return verifyOperator(env, publicKeyText(key.Public().(ed25519.PublicKey)), q.Audience, q.Instance, time.Now())
}
