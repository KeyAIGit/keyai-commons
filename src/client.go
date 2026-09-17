package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"sync"
	"time"
)

type SavedClient struct {
	Config NetworkConfig `json:"config"`
	NodeID string        `json:"node_id"`
	Token  string        `json:"token"`
}
type Client struct {
	mu           sync.Mutex
	connecting   bool
	duty         int
	dir          string
	saved        SavedClient
	consent      bool
	consentUntil time.Time
	status       string
	lastError    string
	lastContact  time.Time
	progress     int
	total        int
	round        int
	activeJob    string
	completed    map[string]bool
	pending      *Result
	accepted     int
	busy         bool
	cancel       context.CancelFunc
	http         *http.Client
	done         context.Context
	shutdown     context.CancelFunc
	modelVersion int
}

func newClient(ctx context.Context, dir string) (*Client, error) {
	if e := os.MkdirAll(dir, 0700); e != nil {
		return nil, e
	}
	done, shutdown := context.WithCancel(ctx)
	c := &Client{duty: 25, dir: dir, http: newHTTPClient(), status: "not_connected", completed: map[string]bool{}, done: done, shutdown: shutdown}
	b, e := os.ReadFile(filepath.Join(dir, "client-private.json"))
	if e == nil {
		if e = json.Unmarshal(b, &c.saved); e != nil {
			return nil, e
		}
		if _, e = decodeConfig(encodeConfig(c.saved.Config)); e != nil {
			return nil, e
		}
		if e = checkNetworkBuildPolicy(c.saved.Config.URL); e != nil {
			return nil, e
		}
		c.status = "paused"
	} else if !os.IsNotExist(e) {
		return nil, e
	}
	// Consent is intentionally never loaded from disk.
	return c, nil
}
func (c *Client) connect(code string) error {
	conf, e := decodeConfig(code)
	if e != nil {
		return e
	}
	if e = checkNetworkBuildPolicy(conf.URL); e != nil {
		return e
	}
	c.mu.Lock()
	if c.busy || c.consent || c.connecting {
		c.mu.Unlock()
		return errors.New("pause participation before changing network")
	}
	if c.saved.Token != "" && c.saved.Config == conf {
		c.mu.Unlock()
		return nil
	}
	c.connecting = true
	c.mu.Unlock()
	defer func() { c.mu.Lock(); c.connecting = false; c.mu.Unlock() }()
	var joined JoinResponse
	if e = postJSON(c.http, conf.URL+"/v1/join", "", JoinRequest{conf.Invite, runtime.GOOS, runtime.GOARCH}, &joined); e != nil {
		return e
	}
	if len(joined.NodeID) < 16 || len(joined.Token) < 32 {
		return errors.New("invalid registration response")
	}
	saved := SavedClient{conf, joined.NodeID, joined.Token}
	if e = atomicJSON(filepath.Join(c.dir, "client-private.json"), saved); e != nil {
		return e
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	c.saved = saved
	c.status = "paused"
	c.lastError = ""
	c.completed = map[string]bool{}
	c.pending = nil
	return nil
}
func (c *Client) allow(minutes int) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.saved.Token == "" || c.connecting {
		return errors.New("finish joining a network first")
	}
	if minutes < 1 || minutes > 60 {
		return errors.New("choose between 1 and 60 minutes")
	}
	if c.consent || c.busy {
		return errors.New("pause before changing session duration")
	}
	c.consent = true
	c.consentUntil = time.Now().Add(time.Duration(minutes) * time.Minute)
	c.status = "waiting_for_operator"
	c.lastError = ""
	return nil
}
func (c *Client) pause() {
	c.mu.Lock()
	c.consent = false
	c.consentUntil = time.Time{}
	c.pending = nil
	if c.cancel != nil {
		c.cancel()
	}
	c.status = "paused"
	c.mu.Unlock()
}
func (c *Client) loop() {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-c.done.Done():
			c.pause()
			return
		case <-ticker.C:
			c.tick()
		}
	}
}
func (c *Client) tick() {
	c.mu.Lock()
	if c.consent && time.Now().After(c.consentUntil) {
		c.consent = false
		c.pending = nil
		if c.cancel != nil {
			c.cancel()
		}
		c.status = "session_finished"
	}
	if c.saved.Token == "" {
		c.mu.Unlock()
		return
	}
	saved := c.saved
	ready := c.consent
	pending := c.pending
	c.mu.Unlock()
	// Retry a computed result instead of retraining if the previous upload failed.
	if pending != nil && ready {
		err := postJSON(c.http, saved.Config.URL+"/v1/result", saved.Token, pending, nil)
		c.mu.Lock()
		if err == nil && c.pending == pending {
			c.pending = nil
			c.accepted++
			c.status = "contribution_verified"
			c.lastError = ""
		} else if err != nil {
			c.lastError = err.Error()
		}
		c.mu.Unlock()
	}
	var p PollResponse
	err := postJSON(c.http, saved.Config.URL+"/v1/poll", saved.Token, PollRequest{ready}, &p)
	c.mu.Lock()
	defer c.mu.Unlock()
	if err != nil {
		c.lastError = "Coordinator unavailable. " + err.Error()
		if c.cancel != nil {
			c.cancel()
		}
		if c.consent {
			c.status = "network_unavailable"
		}
		return
	}
	// A user may have changed network while the request was in flight.
	if saved.Token != c.saved.Token {
		return
	}
	c.lastContact = time.Now()
	c.modelVersion = p.ModelVersion
	if c.busy && p.ActiveRound != c.round {
		if c.cancel != nil {
			c.cancel()
		}
		c.status = "operator_stopped"
	}
	if c.pending != nil && p.ActiveRound != c.round {
		c.pending = nil
	}
	if !c.consent {
		return
	}
	if p.Job == nil {
		if !c.busy && c.pending == nil {
			c.status = "waiting_for_operator"
		}
		return
	}
	j, e := verifyJob(*p.Job, c.saved.Config.PublicKey, c.saved.NodeID, time.Now())
	if e != nil {
		c.lastError = e.Error()
		c.status = "task_rejected"
		return
	}
	if c.completed[j.ID] || c.busy || c.pending != nil {
		return
	}
	c.completed[j.ID] = true
	if len(c.completed) > 1000 {
		c.completed = map[string]bool{j.ID: true}
	}
	until := time.Unix(j.Expires, 0)
	if c.consentUntil.Before(until) {
		until = c.consentUntil
	}
	hard := time.Now().Add(30 * time.Second)
	if hard.Before(until) {
		until = hard
	}
	ctx, cancel := context.WithDeadline(c.done, until)
	c.cancel = cancel
	c.busy = true
	c.activeJob = j.ID
	c.round = j.Round
	c.total = j.Steps
	c.progress = 0
	c.status = "training"
	c.lastError = ""
	go c.perform(ctx, j, cancel, saved.Token)
}
func (c *Client) perform(ctx context.Context, j Job, cancel context.CancelFunc, token string) {
	defer cancel()
	c.mu.Lock()
	duty := c.duty
	c.mu.Unlock()
	w, e := trainWithDuty(ctx, j.Weights, j.Seed, j.Steps, duty, func(i int) { c.mu.Lock(); c.progress = i; c.mu.Unlock() })
	c.mu.Lock()
	defer c.mu.Unlock()
	c.busy = false
	c.cancel = nil
	if e != nil {
		if c.consent {
			c.status = "task_cancelled"
		}
		c.lastError = e.Error()
		return
	}
	if !c.consent || time.Now().After(c.consentUntil) || token != c.saved.Token {
		c.status = "paused"
		return
	}
	// The only model written here is this task's small local training result.
	// This is not a distributed shard store, and not a global checkpoint.
	if e = atomicJSON(filepath.Join(c.dir, "last-local-model.json"), map[string]any{"model": modelID, "round": j.Round, "base_version": j.BaseVersion, "weights": w, "sha256": hashWeights(w), "scope": "local_unaggregated_update"}); e != nil {
		c.lastError = e.Error()
		c.status = "storage_error"
		return
	}
	c.pending = &Result{j.ID, w}
	c.status = "upload_pending"
}
func (c *Client) handler(host, token string) http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		serveAsset(w, "client.html")
	})
	m.HandleFunc("GET /api/status", func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		defer c.mu.Unlock()
		writeJSON(w, 200, map[string]any{"version": version, "status": c.status, "connected": c.saved.Token != "", "network_url": c.saved.Config.URL, "public_key": c.saved.Config.PublicKey, "node_id": c.saved.NodeID, "consent": c.consent, "consent_until": c.consentUntil.Unix(), "busy": c.busy, "round": c.round, "progress": c.progress, "total": c.total, "accepted_this_session": c.accepted, "model_version": c.modelVersion, "last_error": c.lastError, "last_contact": c.lastContact.Unix(), "platform": runtime.GOOS + "/" + runtime.GOARCH, "model": modelID, "parameters": weightCount, "gpu_enabled": false, "cpu_duty_target": c.duty, "connecting": c.connecting, "reachable": !c.lastContact.IsZero() && time.Since(c.lastContact) < 15*time.Second, "internet_enabled": modernToolchain(), "toolchain": runtime.Version()})
	})
	m.HandleFunc("POST /api/connect", func(w http.ResponseWriter, r *http.Request) {
		var q struct {
			Code string `json:"code"`
		}
		if e := readJSON(w, r, &q); e != nil {
			apiError(w, 400, "invalid connection code")
			return
		}
		if e := c.connect(q.Code); e != nil {
			apiError(w, 400, e.Error())
			return
		}
		writeJSON(w, 200, map[string]bool{"connected": true})
	})
	m.HandleFunc("POST /api/discover", c.discoverHandler)
	m.HandleFunc("POST /api/settings", c.settingsHandler)
	m.HandleFunc("POST /api/forget", c.forgetHandler)
	m.HandleFunc("POST /api/consent", func(w http.ResponseWriter, r *http.Request) {
		var q struct {
			Allow        bool `json:"allow"`
			Minutes      int  `json:"minutes"`
			Acknowledged bool `json:"acknowledged"`
		}
		if e := readJSON(w, r, &q); e != nil || !q.Acknowledged {
			apiError(w, 400, "explicit consent is required")
			return
		}
		if !q.Allow {
			c.pause()
		} else if e := c.allow(q.Minutes); e != nil {
			apiError(w, 400, e.Error())
			return
		}
		writeJSON(w, 200, map[string]bool{"ok": true})
	})
	m.HandleFunc("POST /api/pause", func(w http.ResponseWriter, r *http.Request) {
		c.pause()
		writeJSON(w, 200, map[string]bool{"paused": true})
	})
	m.HandleFunc("POST /api/exit", func(w http.ResponseWriter, r *http.Request) {
		c.pause()
		writeJSON(w, 200, map[string]bool{"exiting": true})
		go func() { time.Sleep(150 * time.Millisecond); c.shutdown() }()
	})
	return secureLocal(m, host, token)
}
func runClient(ctx context.Context, dir string, noBrowser bool) (*Client, func(), error) {
	c, e := newClient(ctx, dir)
	if e != nil {
		return nil, nil, e
	}
	ln, e := net.Listen("tcp", "127.0.0.1:0")
	if e != nil {
		return nil, nil, e
	}
	token := randomToken(32)
	ui := "http://" + ln.Addr().String() + "/#" + token
	server := hardenedServer(c.handler(ln.Addr().String(), token))
	if e = atomicJSON(filepath.Join(dir, "local-session-private.json"), map[string]string{"ui_url": ui}); e != nil {
		ln.Close()
		return nil, nil, e
	}
	fmt.Println("KeyAI Commons participant | CPU-only research pilot | close this window to stop")
	if !noBrowser {
		fmt.Println("Local dashboard (PRIVATE): " + ui)
	} else {
		fmt.Println("Local dashboard URL saved to local-session-private.json (not logged)")
	}
	go func() { _ = server.Serve(ln) }()
	go c.loop()
	if !noBrowser {
		openBrowser(ui)
	}
	cleanup := func() { c.shutdown(); c.pause(); _ = server.Close() }
	return c, cleanup, nil
}
