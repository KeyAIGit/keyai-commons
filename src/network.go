package main

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// GETs use the same no-redirect client as signed-job transport. Discovery is
// explicit trust-on-first-use over HTTPS; it does not silently rotate a pin.
func getJSON(client *http.Client, endpoint string, out any) error {
	res, err := client.Get(endpoint)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	b, err := io.ReadAll(io.LimitReader(res.Body, maxBody+1))
	if err != nil {
		return err
	}
	if len(b) > maxBody {
		return errors.New("response too large")
	}
	if res.StatusCode != 200 {
		return errors.New("endpoint unavailable or enrollment is closed")
	}
	return json.Unmarshal(b, out)
}
func checkedOrigin(raw string) (string, error) {
	raw = strings.TrimRight(strings.TrimSpace(raw), "/")
	u, e := url.Parse(raw)
	if e != nil || u.Host == "" || u.User != nil || u.Path != "" || u.RawQuery != "" || u.Fragment != "" {
		return "", errors.New("enter only the coordinator HTTPS origin")
	}
	if u.Scheme != "https" && !(u.Scheme == "http" && isLoopbackOrigin(raw)) {
		return "", errors.New("HTTPS is required outside local testing")
	}
	if e := checkNetworkBuildPolicy(raw); e != nil {
		return "", e
	}
	return raw, nil
}
func (c *Client) discoverHandler(w http.ResponseWriter, r *http.Request) {
	var q struct {
		URL string `json:"url"`
	}
	if readJSON(w, r, &q) != nil {
		apiError(w, 400, "invalid coordinator URL")
		return
	}
	origin, e := checkedOrigin(q.URL)
	if e != nil {
		apiError(w, 400, e.Error())
		return
	}
	var info struct {
		Code string `json:"connection_code"`
	}
	if e = getJSON(c.http, origin+"/v1/connect", &info); e != nil {
		apiError(w, 400, e.Error())
		return
	}
	conf, e := decodeConfig(info.Code)
	if e != nil || conf.URL != origin {
		apiError(w, 400, "discovery origin does not match the connection code")
		return
	}
	if e = c.connect(info.Code); e != nil {
		apiError(w, 400, e.Error())
		return
	}
	writeJSON(w, 200, map[string]bool{"connected": true})
}
func (c *Client) settingsHandler(w http.ResponseWriter, r *http.Request) {
	var q struct {
		Duty int `json:"cpu_duty_target"`
	}
	if readJSON(w, r, &q) != nil || (q.Duty != 10 && q.Duty != 25 && q.Duty != 50) {
		apiError(w, 400, "choose 10, 25 or 50 percent of one logical CPU")
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.consent || c.busy {
		apiError(w, 409, "pause before changing the CPU pacing target")
		return
	}
	c.duty = q.Duty
	writeJSON(w, 200, map[string]bool{"ok": true})
}
func (c *Client) forgetHandler(w http.ResponseWriter, r *http.Request) {
	c.pause()
	c.mu.Lock()
	if c.busy || c.connecting {
		c.mu.Unlock()
		apiError(w, 409, "work is stopping; retry once paused")
		return
	}
	c.connecting = true
	saved := c.saved
	c.mu.Unlock()
	defer func() { c.mu.Lock(); c.connecting = false; c.mu.Unlock() }()
	// Revocation must reach the server before removing the local authentication
	// key. A network outage leaves the client paused and able to retry.
	if saved.Token != "" {
		if e := postJSON(c.http, saved.Config.URL+"/v1/leave", saved.Token, struct{}{}, nil); e != nil {
			apiError(w, 503, "revocation failed; client is paused, retry when coordinator is available")
			return
		}
	}
	for _, name := range []string{"client-private.json", "last-local-model.json"} {
		if e := os.Remove(filepath.Join(c.dir, name)); e != nil && !os.IsNotExist(e) {
			apiError(w, 500, "local state removal failed")
			return
		}
	}
	c.mu.Lock()
	c.saved = SavedClient{}
	c.pending = nil
	c.completed = map[string]bool{}
	c.lastError = ""
	c.status = "not_connected"
	c.lastContact = time.Time{}
	c.mu.Unlock()
	writeJSON(w, 200, map[string]bool{"forgotten": true})
}
func (c *Coordinator) connectionInfo(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if !c.publicEnrollment {
		apiError(w, 403, "public enrollment is closed; ask the organizer for an invitation")
		return
	}
	writeJSON(w, 200, map[string]any{"connection_code": encodeConfig(c.config), "url": c.config.URL, "public_key": c.config.PublicKey, "pilot": true, "persistence": c.persistence})
}
func (c *Coordinator) leave(w http.ResponseWriter, r *http.Request) {
	var q struct{}
	if readJSON(w, r, &q) != nil {
		apiError(w, 400, "invalid revocation")
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	n, ok := c.authenticate(r)
	if !ok { // Idempotent without revealing whether a node ever existed.
		writeJSON(w, 200, map[string]bool{"revoked": true})
		return
	}
	delete(c.state.Nodes, n.ID)
	if e := c.saveLocked(); e != nil {
		c.state.Nodes[n.ID] = n
		apiError(w, 500, "revocation persistence failed")
		return
	}
	delete(c.authIndex, n.TokenHash)
	delete(c.lastPoll, n.ID)
	if a := c.active; a != nil {
		delete(a.Jobs, n.ID)
		delete(a.Results, n.ID)
		delete(a.Verifying, n.ID)
	}
	writeJSON(w, 200, map[string]bool{"revoked": true})
}
func (c *Coordinator) reclaimLocked() {
	a := c.active
	if a == nil {
		return
	}
	cutoff := time.Now().Unix() - 12
	for id := range a.Jobs {
		if _, ok := a.Results[id]; ok || a.Verifying[id] {
			continue
		}
		n := c.state.Nodes[id]
		if n == nil || !n.Ready || n.LastSeen < cutoff {
			delete(a.Jobs, id)
			a.Reassigned++
		}
	}
}
