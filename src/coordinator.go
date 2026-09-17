package main

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"math"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"
)

type Node struct {
	ID        string `json:"id"`
	TokenHash string `json:"token_hash"`
	OS        string `json:"os"`
	Arch      string `json:"arch"`
	LastSeen  int64  `json:"last_seen"`
	Ready     bool   `json:"ready"`
	Verified  int    `json:"verified"`
	LastJob   string `json:"last_job,omitempty"`
}
type Record struct {
	Round        int     `json:"round"`
	Version      int     `json:"version"`
	Participants int     `json:"participants"`
	Loss         float64 `json:"loss"`
	Accuracy     float64 `json:"accuracy"`
	Time         int64   `json:"time"`
	Hash         string  `json:"hash"`
}
type ModelState struct {
	Model   string    `json:"model"`
	Version int       `json:"version"`
	Weights []float64 `json:"weights"`
	Hash    string    `json:"hash"`
}
type Persistent struct {
	Model   ModelState       `json:"model"`
	Nodes   map[string]*Node `json:"nodes"`
	Counter int              `json:"counter"`
	History []Record         `json:"history"`
}
type Identity struct {
	PrivateKey string `json:"private_key"`
	Invite     string `json:"invite"`
}
type Round struct {
	Number    int
	Deadline  int64
	Jobs      map[string]Job
	Results   map[string][]float64
	Verifying map[string]bool
	Steps     int
	Goal      int
}
type Coordinator struct {
	mu           sync.Mutex
	dir          string
	key          ed25519.PrivateKey
	config       NetworkConfig
	state        Persistent
	active       *Round
	lastError    string
	joinAttempts map[string][]int64
	lastPoll     map[string]time.Time
	verifySlots  chan struct{}
}

func newCoordinator(dir, publicURL string) (*Coordinator, error) {
	if e := os.MkdirAll(dir, 0700); e != nil {
		return nil, e
	}
	c := &Coordinator{dir: dir, joinAttempts: map[string][]int64{}, lastPoll: map[string]time.Time{}, verifySlots: make(chan struct{}, 2)}
	var id Identity
	b, e := os.ReadFile(filepath.Join(dir, "identity-private.json"))
	if os.IsNotExist(e) {
		_, key, err := ed25519.GenerateKey(rand.Reader)
		if err != nil {
			return nil, err
		}
		id = Identity{base64.RawURLEncoding.EncodeToString(key), randomToken(24)}
		if err = atomicJSON(filepath.Join(dir, "identity-private.json"), id); err != nil {
			return nil, err
		}
	} else if e != nil {
		return nil, e
	} else if e = json.Unmarshal(b, &id); e != nil {
		return nil, e
	}
	key, e := base64.RawURLEncoding.DecodeString(id.PrivateKey)
	if e != nil || len(key) != 64 {
		return nil, errors.New("invalid saved server identity")
	}
	c.key = ed25519.PrivateKey(key)
	c.config = NetworkConfig{strings.TrimRight(publicURL, "/"), publicKeyText(c.key.Public().(ed25519.PublicKey)), id.Invite}
	if _, e = decodeConfig(encodeConfig(c.config)); e != nil {
		return nil, e
	}
	b, e = os.ReadFile(filepath.Join(dir, "state-private.json"))
	if os.IsNotExist(e) {
		w := initialWeights()
		c.state = Persistent{Model: ModelState{modelID, 0, w, hashWeights(w)}, Nodes: map[string]*Node{}, History: []Record{}}
	} else if e != nil {
		return nil, e
	} else if e = json.Unmarshal(b, &c.state); e != nil {
		return nil, e
	}
	if !validWeights(c.state.Model.Weights) || c.state.Model.Hash != hashWeights(c.state.Model.Weights) || c.state.Model.Model != modelID {
		return nil, errors.New("saved model failed integrity check")
	}
	if c.state.Nodes == nil {
		c.state.Nodes = map[string]*Node{}
	}
	// Restart never resumes a training campaign without another operator command.
	for _, n := range c.state.Nodes {
		n.Ready = false
		n.LastSeen = 0
	}
	if e = c.saveLocked(); e != nil {
		return nil, e
	}
	return c, nil
}
func (c *Coordinator) saveLocked() error {
	return atomicJSON(filepath.Join(c.dir, "state-private.json"), c.state)
}
func (c *Coordinator) authenticate(r *http.Request) (*Node, bool) {
	token := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
	if len(token) < 32 {
		return nil, false
	}
	hash := tokenHash(token)
	for _, n := range c.state.Nodes {
		if secureEqual(n.TokenHash, hash) {
			return n, true
		}
	}
	return nil, false
}
func (c *Coordinator) publicHandler() http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		serveAsset(w, "landing.html")
	})
	m.HandleFunc("GET /v1/info", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"name": "KeyAI Commons", "version": version, "model": modelID, "public_key": c.config.PublicKey, "pilot": true, "max_registered_nodes": 256, "max_nodes_per_round": 32})
	})
	m.HandleFunc("GET /v1/status", c.status)
	m.HandleFunc("GET /v1/model", func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		defer c.mu.Unlock()
		writeJSON(w, 200, c.state.Model)
	})
	m.HandleFunc("POST /v1/join", c.join)
	m.HandleFunc("POST /v1/poll", c.poll)
	m.HandleFunc("POST /v1/result", c.result)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { securityHeaders(w); m.ServeHTTP(w, r) })
}
func (c *Coordinator) join(w http.ResponseWriter, r *http.Request) {
	var q JoinRequest
	if e := readJSON(w, r, &q); e != nil {
		apiError(w, 400, "invalid registration")
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	ip, _, _ := net.SplitHostPort(r.RemoteAddr)
	now := time.Now().Unix()
	times := c.joinAttempts[ip]
	recent := times[:0]
	for _, t := range times {
		if t > now-3600 {
			recent = append(recent, t)
		}
	}
	if len(recent) >= 20 {
		apiError(w, 429, "registration limit; retry later")
		return
	}
	if len(c.joinAttempts) > 1024 {
		c.joinAttempts = map[string][]int64{}
	}
	c.joinAttempts[ip] = append(recent, now)
	if !secureEqual(q.Invite, c.config.Invite) {
		apiError(w, 403, "invitation rejected")
		return
	}
	if len(q.OS) > 20 || len(q.Arch) > 20 || len(c.state.Nodes) >= 256 {
		apiError(w, 409, "pilot enrollment limit or invalid platform")
		return
	}
	id, token := randomToken(16), randomToken(32)
	c.state.Nodes[id] = &Node{ID: id, TokenHash: tokenHash(token), OS: q.OS, Arch: q.Arch, LastSeen: now}
	if e := c.saveLocked(); e != nil {
		delete(c.state.Nodes, id)
		apiError(w, 500, "registration could not be persisted")
		return
	}
	writeJSON(w, 200, JoinResponse{id, token})
}
func (c *Coordinator) poll(w http.ResponseWriter, r *http.Request) {
	var q PollRequest
	if e := readJSON(w, r, &q); e != nil {
		apiError(w, 400, "invalid poll")
		return
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	n, ok := c.authenticate(r)
	if !ok {
		apiError(w, 401, "node authentication required")
		return
	}
	if time.Since(c.lastPoll[n.ID]) < 200*time.Millisecond {
		apiError(w, 429, "polling too frequently")
		return
	}
	c.lastPoll[n.ID] = time.Now()
	n.LastSeen = time.Now().Unix()
	n.Ready = q.Ready
	c.expireLocked()
	out := PollResponse{State: "waiting", ModelVersion: c.state.Model.Version}
	if c.active != nil {
		a := c.active
		out.ActiveRound = a.Number
		out.State = "round_in_progress"
		if q.Ready {
			if _, done := a.Results[n.ID]; !done {
				job, assigned := a.Jobs[n.ID]
				if !assigned && len(a.Jobs) < a.Goal {
					var seed [8]byte
					_, _ = rand.Read(seed[:])
					s := binary.LittleEndian.Uint64(seed[:])
					if s == 0 {
						s = 1
					}
					job = Job{protocolVersion, modelID, randomToken(18), n.ID, a.Number, c.state.Model.Version, c.state.Model.Hash, append([]float64(nil), c.state.Model.Weights...), s, a.Steps, time.Now().Unix(), a.Deadline}
					a.Jobs[n.ID] = job
					assigned = true
				}
				if assigned {
					env, e := signJob(c.key, job)
					if e != nil {
						apiError(w, 500, "cannot sign task")
						return
					}
					out.Job = &env
					out.State = "assigned"
				}
			} else {
				out.State = "contribution_verified"
			}
		}
	}
	writeJSON(w, 200, out)
}
func (c *Coordinator) result(w http.ResponseWriter, r *http.Request) {
	var q Result
	if e := readJSON(w, r, &q); e != nil || !validWeights(q.Weights) {
		apiError(w, 400, "invalid model update")
		return
	}
	c.mu.Lock()
	n, ok := c.authenticate(r)
	if !ok {
		c.mu.Unlock()
		apiError(w, 401, "node authentication required")
		return
	}
	if n.LastJob == q.JobID {
		c.mu.Unlock()
		writeJSON(w, 200, map[string]any{"accepted": true, "duplicate": true})
		return
	}
	c.expireLocked()
	a := c.active
	if a == nil {
		c.mu.Unlock()
		apiError(w, 409, "round closed")
		return
	}
	job, ok := a.Jobs[n.ID]
	if !ok || job.ID != q.JobID {
		c.mu.Unlock()
		apiError(w, 409, "job was not assigned to this node")
		return
	}
	if _, done := a.Results[n.ID]; done {
		c.mu.Unlock()
		writeJSON(w, 200, map[string]any{"accepted": true, "duplicate": true})
		return
	}
	if a.Verifying[n.ID] {
		c.mu.Unlock()
		apiError(w, 409, "result verification already in progress")
		return
	}
	select {
	case c.verifySlots <- struct{}{}:
	default:
		c.mu.Unlock()
		apiError(w, 429, "verification capacity busy; retry")
		return
	}
	a.Verifying[n.ID] = true
	nodeID := n.ID
	c.mu.Unlock()
	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	expected, err := trainModel(ctx, job.Weights, job.Seed, job.Steps, false, nil)
	cancel()
	<-c.verifySlots
	honest := err == nil && len(expected) == len(q.Weights)
	if honest {
		for i, v := range expected {
			if math.Abs(v-q.Weights[i]) > 1e-7*(1+math.Abs(v)) {
				honest = false
				break
			}
		}
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	delete(a.Verifying, nodeID)
	if c.active != a || time.Now().Unix() >= a.Deadline {
		c.expireLocked()
		apiError(w, 409, "round expired during verification")
		return
	}
	if !honest {
		apiError(w, 422, "update failed deterministic reference replay")
		return
	}
	a.Results[nodeID] = expected // canonical reference values avoid platform rounding drift.
	n.LastSeen = time.Now().Unix()
	if len(a.Results) >= a.Goal {
		if e := c.finalizeLocked(); e != nil {
			apiError(w, 500, "checkpoint persistence failed")
			return
		}
	}
	writeJSON(w, 200, map[string]any{"accepted": true, "verification": "full_reference_replay", "note": "pilot verifier repeats the work; no compute saving is claimed"})
}
func (c *Coordinator) expireLocked() {
	if c.active != nil && time.Now().Unix() >= c.active.Deadline {
		_ = c.finalizeLocked()
	}
}
func (c *Coordinator) finalizeLocked() error {
	a := c.active
	if a == nil {
		return errors.New("no active round")
	}
	if len(a.Results) == 0 {
		c.active = nil
		return nil
	}
	ids := make([]string, 0, len(a.Results))
	for id := range a.Results {
		ids = append(ids, id)
	}
	sort.Strings(ids)
	w := make([]float64, weightCount)
	for _, id := range ids {
		for j, v := range a.Results[id] {
			w[j] += v / float64(len(ids))
		}
	}
	if !validWeights(w) {
		c.active = nil
		return errors.New("invalid aggregate")
	}
	oldModel := c.state.Model
	oldHistory := append([]Record(nil), c.state.History...)
	c.state.Model = ModelState{modelID, c.state.Model.Version + 1, w, hashWeights(w)}
	loss, acc := evaluate(w)
	c.state.History = append(c.state.History, Record{a.Number, c.state.Model.Version, len(ids), loss, acc, time.Now().Unix(), hashWeights(w)})
	if len(c.state.History) > 1000 {
		c.state.History = c.state.History[len(c.state.History)-1000:]
	}
	oldJobs := map[string]string{}
	for _, id := range ids {
		oldJobs[id] = c.state.Nodes[id].LastJob
		c.state.Nodes[id].LastJob = a.Jobs[id].ID
		c.state.Nodes[id].Verified++
	}
	if e := c.saveLocked(); e != nil {
		c.state.Model = oldModel
		c.state.History = oldHistory
		for _, id := range ids {
			c.state.Nodes[id].Verified--
			c.state.Nodes[id].LastJob = oldJobs[id]
		}
		c.active = nil
		c.lastError = "checkpoint write failed; round aborted"
		return e
	}
	c.active = nil
	c.lastError = ""
	return nil
}
func (c *Coordinator) startRound(steps, goal, seconds int) error {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.expireLocked()
	if c.active != nil {
		return errors.New("a round is already active")
	}
	if steps < 10 || steps > maxSteps || goal < 1 || goal > 32 || seconds < 30 || seconds > 240 {
		return errors.New("pilot limits: 10..1200 steps, 1..32 nodes, 30..240 seconds")
	}
	c.state.Counter++
	if e := c.saveLocked(); e != nil {
		c.state.Counter--
		return e
	}
	c.active = &Round{Number: c.state.Counter, Deadline: time.Now().Unix() + int64(seconds), Jobs: map[string]Job{}, Results: map[string][]float64{}, Verifying: map[string]bool{}, Steps: steps, Goal: goal}
	return nil
}
func (c *Coordinator) status(w http.ResponseWriter, r *http.Request) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.expireLocked()
	online, ready, contrib := 0, 0, 0
	for _, n := range c.state.Nodes {
		if n.LastSeen > time.Now().Unix()-15 {
			online++
			if n.Ready {
				ready++
			}
		}
		contrib += n.Verified
	}
	loss, acc := evaluate(c.state.Model.Weights)
	active := map[string]any{"running": false}
	if a := c.active; a != nil {
		active = map[string]any{"running": true, "number": a.Number, "deadline": a.Deadline, "assigned": len(a.Jobs), "verified": len(a.Results), "target": a.Goal, "steps": a.Steps}
	}
	writeJSON(w, 200, map[string]any{"name": "KeyAI Commons", "version": version, "pilot": true, "model": modelID, "parameters": weightCount, "registered": len(c.state.Nodes), "online": online, "ready": ready, "verified_contributions": contrib, "model_version": c.state.Model.Version, "model_hash": c.state.Model.Hash, "loss": loss, "accuracy": acc, "history": c.state.History, "round": active, "error": c.lastError})
}
func (c *Coordinator) adminHandler(host, token string) http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		serveAsset(w, "admin.html")
	})
	m.HandleFunc("GET /api/status", c.status)
	m.HandleFunc("GET /api/config", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"connection_code": encodeConfig(c.config), "public_url": c.config.URL, "public_key": c.config.PublicKey, "version": version})
	})
	m.HandleFunc("POST /api/start", func(w http.ResponseWriter, r *http.Request) {
		var q struct {
			Steps   int `json:"steps"`
			Nodes   int `json:"nodes"`
			Seconds int `json:"seconds"`
		}
		if e := readJSON(w, r, &q); e != nil {
			apiError(w, 400, "invalid round settings")
			return
		}
		if e := c.startRound(q.Steps, q.Nodes, q.Seconds); e != nil {
			apiError(w, 409, e.Error())
			return
		}
		writeJSON(w, 200, map[string]bool{"started": true})
	})
	m.HandleFunc("POST /api/stop", func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		c.active = nil
		c.mu.Unlock()
		writeJSON(w, 200, map[string]bool{"stopped": true})
	})
	m.HandleFunc("POST /api/finalize", func(w http.ResponseWriter, r *http.Request) {
		c.mu.Lock()
		defer c.mu.Unlock()
		if e := c.finalizeLocked(); e != nil {
			apiError(w, 409, e.Error())
			return
		}
		writeJSON(w, 200, map[string]bool{"finalized": true})
	})
	return secureLocal(m, host, token)
}
func runCoordinator(ctx context.Context, dir, listen, publicURL string, noBrowser bool) (*Coordinator, func(), error) {
	if e := checkListenBuildPolicy(listen); e != nil {
		return nil, nil, e
	}
	listener, e := net.Listen("tcp", listen)
	if e != nil {
		return nil, nil, e
	}
	if publicURL == "" {
		publicURL = "http://" + listener.Addr().String()
	}
	if e := checkNetworkBuildPolicy(publicURL); e != nil {
		listener.Close()
		return nil, nil, e
	}
	c, e := newCoordinator(dir, publicURL)
	if e != nil {
		listener.Close()
		return nil, nil, e
	}
	admin, e := net.Listen("tcp", "127.0.0.1:0")
	if e != nil {
		listener.Close()
		return nil, nil, e
	}
	token := randomToken(32)
	adminURL := "http://" + admin.Addr().String() + "/#" + token
	server := hardenedServer(c.publicHandler())
	adminServer := hardenedServer(c.adminHandler(admin.Addr().String(), token))
	if e = atomicJSON(filepath.Join(dir, "operator-session-private.json"), map[string]string{"admin_url": adminURL, "public_url": publicURL, "connection_code": encodeConfig(c.config)}); e != nil {
		listener.Close()
		admin.Close()
		return nil, nil, e
	}
	fmt.Println("KeyAI Commons coordinator (bounded pilot, not a public production service)")
	fmt.Println("Operator dashboard (PRIVATE): " + adminURL)
	fmt.Println("Network endpoint: " + publicURL)
	go func() { _ = server.Serve(listener) }()
	go func() { _ = adminServer.Serve(admin) }()
	go func() {
		timer := time.NewTicker(time.Second)
		defer timer.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-timer.C:
				c.mu.Lock()
				c.expireLocked()
				c.mu.Unlock()
			}
		}
	}()
	if !noBrowser {
		openBrowser(adminURL)
	}
	closeFn := func() {
		_ = server.Close()
		_ = adminServer.Close()
		c.mu.Lock()
		c.active = nil
		for _, n := range c.state.Nodes {
			n.Ready = false
		}
		_ = c.saveLocked()
		c.mu.Unlock()
	}
	return c, closeFn, nil
}
func hardenedServer(h http.Handler) *http.Server {
	return &http.Server{Handler: h, ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 10 * time.Second, WriteTimeout: 15 * time.Second, IdleTimeout: 20 * time.Second, MaxHeaderBytes: 8192}
}
