package main

import (
	"bytes"
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/json"
	"math"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func testCo(t *testing.T) (*Coordinator, *httptest.Server) {
	t.Helper()
	c, e := newCoordinator(t.TempDir(), "http://127.0.0.1:18741")
	if e != nil {
		t.Fatal(e)
	}
	s := httptest.NewServer(c.publicHandler())
	c.config.URL = s.URL
	t.Cleanup(s.Close)
	return c, s
}
func enroll(t *testing.T, c *Coordinator, s *httptest.Server) JoinResponse {
	t.Helper()
	var n JoinResponse
	if e := postJSON(newHTTPClient(), s.URL+"/v1/join", "", JoinRequest{c.config.Invite, "test", "amd64"}, &n); e != nil {
		t.Fatal(e)
	}
	return n
}
func assignment(t *testing.T, c *Coordinator, s *httptest.Server, n JoinResponse) Job {
	t.Helper()
	var p PollResponse
	if e := postJSON(newHTTPClient(), s.URL+"/v1/poll", n.Token, PollRequest{true}, &p); e != nil {
		t.Fatal(e)
	}
	if p.Job == nil {
		t.Fatal("no assignment")
	}
	j, e := verifyJob(*p.Job, c.config.PublicKey, n.NodeID, time.Now())
	if e != nil {
		t.Fatal(e)
	}
	return j
}
func submit(t *testing.T, s *httptest.Server, n JoinResponse, j Job) {
	t.Helper()
	w, e := trainModel(context.Background(), j.Weights, j.Seed, j.Steps, false, nil)
	if e != nil {
		t.Fatal(e)
	}
	if e = postJSON(newHTTPClient(), s.URL+"/v1/result", n.Token, Result{j.ID, w}, nil); e != nil {
		t.Fatal(e)
	}
}
func TestTrainingReallyLearns(t *testing.T) {
	w := initialWeights()
	l0, a0 := evaluate(w)
	var e error
	for i := 0; i < 5; i++ {
		w, e = trainModel(context.Background(), w, uint64(100+i), 800, false, nil)
		if e != nil {
			t.Fatal(e)
		}
	}
	l, a := evaluate(w)
	t.Logf("initial loss %.6f accuracy %.4f; final loss %.6f accuracy %.4f", l0, a0, l, a)
	if !(l < l0*.5 && a > .9) {
		t.Fatal("no measured learning")
	}
}
func TestDeterministicWorkload(t *testing.T) {
	a, _ := trainModel(context.Background(), initialWeights(), 55, 100, false, nil)
	b, _ := trainModel(context.Background(), initialWeights(), 55, 100, false, nil)
	if hashWeights(a) != hashWeights(b) {
		t.Fatal("not deterministic")
	}
}
func TestAnalyticalGradientFiniteDifference(t *testing.T) {
	w := initialWeights()
	seed := uint64(991)
	r := PRNG{seed}
	type xyz struct{ x, y, l float64 }
	batch := []xyz{}
	for i := 0; i < batchSize; i++ {
		x, y, l := sample(&r)
		batch = append(batch, xyz{x, y, l})
	}
	loss := func(v []float64) float64 {
		sum := 0.0
		for _, a := range batch {
			p, _ := forward(v, a.x, a.y)
			sum -= a.l*math.Log(p) + (1-a.l)*math.Log(1-p)
		}
		return sum / batchSize
	}
	after, _ := trainModel(context.Background(), w, seed, 1, false, nil)
	for i := range w {
		v := append([]float64(nil), w...)
		eps := 1e-5
		v[i] += eps
		p := loss(v)
		v[i] -= 2 * eps
		m := loss(v)
		numeric := (p - m) / (2 * eps)
		analytic := (w[i] - after[i]) / .12
		if math.Abs(numeric-analytic) > 1e-7 {
			t.Fatalf("gradient %d: %g != %g", i, numeric, analytic)
		}
	}
}
func TestRejectInvalidWeights(t *testing.T) {
	for _, x := range []float64{math.NaN(), math.Inf(1), 51} {
		w := initialWeights()
		w[0] = x
		if validWeights(w) {
			t.Fatal("accepted invalid weight")
		}
	}
	if validWeights([]float64{1}) {
		t.Fatal("bad shape")
	}
}
func TestTaskBounds(t *testing.T) {
	for _, steps := range []int{0, -1, maxSteps + 1} {
		if _, e := trainModel(context.Background(), initialWeights(), 1, steps, false, nil); e == nil {
			t.Fatal("unbounded steps accepted")
		}
	}
}
func TestCancellationIsPrompt(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { _, e := trainModel(ctx, initialWeights(), 5, 1200, true, nil); done <- e }()
	time.Sleep(20 * time.Millisecond)
	start := time.Now()
	cancel()
	select {
	case e := <-done:
		if e == nil {
			t.Fatal("cancel ignored")
		}
		if time.Since(start) > 200*time.Millisecond {
			t.Fatal("slow cancel")
		}
	case <-time.After(time.Second):
		t.Fatal("cancel stuck")
	}
}
func TestSignaturesAndTaskPolicy(t *testing.T) {
	pk, key, _ := ed25519.GenerateKey(rand.Reader)
	w := initialWeights()
	j := Job{protocolVersion, modelID, "job", "node", 1, 0, hashWeights(w), w, 1, 100, time.Now().Unix(), time.Now().Add(time.Minute).Unix()}
	env, _ := signJob(key, j)
	if _, e := verifyJob(env, publicKeyText(pk), "node", time.Now()); e != nil {
		t.Fatal(e)
	}
	env.Payload += "A"
	if _, e := verifyJob(env, publicKeyText(pk), "node", time.Now()); e == nil {
		t.Fatal("tamper accepted")
	}
	env, _ = signJob(key, j)
	if _, e := verifyJob(env, publicKeyText(pk), "different-node", time.Now()); e == nil {
		t.Fatal("wrong node accepted")
	}
	if _, e := verifyJob(env, publicKeyText(pk), "node", time.Now().Add(2*time.Minute)); e == nil {
		t.Fatal("expired job accepted")
	}
	j.Model = "remote-shell"
	env, _ = signJob(key, j)
	if _, e := verifyJob(env, publicKeyText(pk), "node", time.Now()); e == nil {
		t.Fatal("unapproved model accepted")
	}
}
func TestConfigRejectsInsecureRemoteURL(t *testing.T) {
	pk, _, _ := ed25519.GenerateKey(rand.Reader)
	for _, u := range []string{"http://example.org", "http://192.168.1.10:9", "https://name:pass@example.org", "https://example.org/a", "file:///tmp/x"} {
		if _, e := decodeConfig(encodeConfig(NetworkConfig{u, publicKeyText(pk), strings.Repeat("a", 24)})); e == nil {
			t.Fatal("insecure config accepted:", u)
		}
	}
}
func TestConfigAcceptsPinnedHTTPSAndLoopback(t *testing.T) {
	pk, _, _ := ed25519.GenerateKey(rand.Reader)
	for _, u := range []string{"https://example.org", "http://127.0.0.1:1234", "http://[::1]:1234"} {
		if _, e := decodeConfig(encodeConfig(NetworkConfig{u, publicKeyText(pk), strings.Repeat("a", 24)})); e != nil {
			t.Fatal(e)
		}
	}
}
func TestNoWorkWithoutOperatorCommand(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	var p PollResponse
	if e := postJSON(newHTTPClient(), s.URL+"/v1/poll", n.Token, PollRequest{true}, &p); e != nil || p.Job != nil {
		t.Fatal("unscheduled training", e)
	}
}
func TestNoAssignmentWithoutConsent(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	var p PollResponse
	if e := postJSON(newHTTPClient(), s.URL+"/v1/poll", n.Token, PollRequest{false}, &p); e != nil || p.Job != nil {
		t.Fatal("work without consent", e)
	}
}
func TestThreeNodeRoundAndCheckpoint(t *testing.T) {
	c, s := testCo(t)
	ns := []JoinResponse{enroll(t, c, s), enroll(t, c, s), enroll(t, c, s)}
	if e := c.startRound(600, 3, 60); e != nil {
		t.Fatal(e)
	}
	for _, n := range ns {
		submit(t, s, n, assignment(t, c, s, n))
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.active != nil || c.state.Model.Version != 1 || len(c.state.History) != 1 || c.state.History[0].Participants != 3 {
		t.Fatal("round did not commit")
	}
	if c.state.History[0].Loss >= .6 {
		t.Fatal("model did not learn")
	}
	b, e := os.ReadFile(filepath.Join(c.dir, "state-private.json"))
	if e != nil {
		t.Fatal(e)
	}
	var p Persistent
	if json.Unmarshal(b, &p) != nil || p.Model.Hash != hashWeights(p.Model.Weights) {
		t.Fatal("bad checkpoint")
	}
}
func TestDropoutDoesNotBlockDeadline(t *testing.T) {
	c, s := testCo(t)
	n1, n2 := enroll(t, c, s), enroll(t, c, s)
	_ = c.startRound(100, 2, 60)
	j := assignment(t, c, s, n1)
	_ = assignment(t, c, s, n2)
	submit(t, s, n1, j)
	c.mu.Lock()
	c.active.Deadline = time.Now().Unix() - 1
	c.expireLocked()
	defer c.mu.Unlock()
	if c.active != nil || c.state.Model.Version != 1 || c.state.History[0].Participants != 1 {
		t.Fatal("dropout blocked aggregation")
	}
}
func TestRejectForgedUpdate(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	j := assignment(t, c, s, n)
	w := append([]float64(nil), j.Weights...)
	w[0] += .5
	e := postJSON(newHTTPClient(), s.URL+"/v1/result", n.Token, Result{j.ID, w}, nil)
	if e == nil || !strings.Contains(e.Error(), "422") {
		t.Fatal("forged result accepted", e)
	}
	if len(c.active.Results) != 0 {
		t.Fatal("forged update stored")
	}
}
func TestDuplicateResultDoesNotDoubleCount(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 2, 60)
	j := assignment(t, c, s, n)
	submit(t, s, n, j)
	submit(t, s, n, j)
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.active.Results) != 1 {
		t.Fatal("duplicate counted")
	}
}
func TestServerRestartNeverResumesCampaign(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	submit(t, s, n, assignment(t, c, s, n))
	_ = c.startRound(100, 1, 60)
	next, e := newCoordinator(c.dir, c.config.URL)
	if e != nil {
		t.Fatal(e)
	}
	if next.active != nil || next.state.Model.Version != 1 {
		t.Fatal("unsafe or lost restart state")
	}
	for _, n := range next.state.Nodes {
		if n.Ready {
			t.Fatal("restored stale consent")
		}
	}
}
func TestClientRestartResetsConsent(t *testing.T) {
	c, s := testCo(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cl, e := newClient(ctx, t.TempDir())
	if e != nil {
		t.Fatal(e)
	}
	if e = cl.connect(encodeConfig(c.config)); e != nil {
		t.Fatal(e)
	}
	_ = s
	_ = cl.allow(15)
	next, e := newClient(ctx, cl.dir)
	if e != nil || next.consent || next.saved.Token == "" {
		t.Fatal("consent persisted or identity lost", e)
	}
}
func TestLocalUIRejectsCSRFAndWrongHost(t *testing.T) {
	m := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(200) })
	h := secureLocal(m, "127.0.0.1:1234", "secret")
	cases := []struct {
		host, origin, token string
		want                int
	}{{"evil.example", "", "secret", 403}, {"127.0.0.1:1234", "https://evil.example", "secret", 403}, {"127.0.0.1:1234", "", "", 401}, {"127.0.0.1:1234", "http://127.0.0.1:1234", "secret", 200}}
	for _, x := range cases {
		r := httptest.NewRequest("POST", "http://127.0.0.1:1234/api/pause", nil)
		r.Host = x.host
		r.Header.Set("Origin", x.origin)
		r.Header.Set("X-Session-Token", x.token)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != x.want {
			t.Fatalf("%+v: %d", x, w.Code)
		}
	}
}
func TestPublicAPIDoesNotExposeAdmin(t *testing.T) {
	_, s := testCo(t)
	for _, path := range []string{"/api/start", "/api/config", "/admin", "/state-private.json", "/identity-private.json"} {
		r, e := http.Post(s.URL+path, "application/json", strings.NewReader("{}"))
		if e != nil {
			t.Fatal(e)
		}
		r.Body.Close()
		if r.StatusCode < 400 {
			t.Fatal("public admin exposure", path)
		}
	}
}
func TestUnauthenticatedNodeDenied(t *testing.T) {
	_, s := testCo(t)
	e := postJSON(newHTTPClient(), s.URL+"/v1/poll", "", PollRequest{true}, nil)
	if e == nil || !strings.Contains(e.Error(), "401") {
		t.Fatal("missing auth accepted")
	}
}
func TestWrongInviteDenied(t *testing.T) {
	_, s := testCo(t)
	e := postJSON(newHTTPClient(), s.URL+"/v1/join", "", JoinRequest{"wrong", "test", "test"}, nil)
	if e == nil {
		t.Fatal("bad invite accepted")
	}
}
func TestOversizedBodyDenied(t *testing.T) {
	_, s := testCo(t)
	res, e := http.Post(s.URL+"/v1/join", "application/json", bytes.NewReader(bytes.Repeat([]byte("x"), maxBody+10)))
	if e != nil {
		t.Fatal(e)
	}
	res.Body.Close()
	if res.StatusCode < 400 {
		t.Fatal("large body accepted")
	}
}
func TestUnknownFieldsDenied(t *testing.T) {
	c, s := testCo(t)
	res, e := http.Post(s.URL+"/v1/join", "application/json", strings.NewReader(`{"invite":"`+c.config.Invite+`","os":"test","arch":"test","shell":"calc.exe"}`))
	if e != nil {
		t.Fatal(e)
	}
	res.Body.Close()
	if res.StatusCode != 400 {
		t.Fatal("unknown command field accepted")
	}
}
func TestModelHashIntegrityOnRestart(t *testing.T) {
	c, _ := testCo(t)
	c.state.Model.Weights[0] += .1
	if e := c.saveLocked(); e != nil {
		t.Fatal(e)
	}
	if _, e := newCoordinator(c.dir, c.config.URL); e == nil {
		t.Fatal("corrupt model accepted")
	}
}
func TestStopRejectsLateResults(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	j := assignment(t, c, s, n)
	c.mu.Lock()
	c.active = nil
	c.mu.Unlock()
	w, _ := trainModel(context.Background(), j.Weights, j.Seed, j.Steps, false, nil)
	if e := postJSON(newHTTPClient(), s.URL+"/v1/result", n.Token, Result{j.ID, w}, nil); e == nil {
		t.Fatal("stopped job accepted")
	}
}
func TestZeroContributionRoundDoesNotChangeModel(t *testing.T) {
	c, _ := testCo(t)
	_ = c.startRound(100, 1, 30)
	c.mu.Lock()
	c.active.Deadline = time.Now().Unix() - 1
	c.expireLocked()
	defer c.mu.Unlock()
	if c.active != nil || c.state.Model.Version != 0 {
		t.Fatal("empty round mutated model")
	}
}
func TestNoThirdPartyPackages(t *testing.T) {
	b, e := os.ReadFile("go.mod")
	if e != nil || strings.Contains(string(b), "require") {
		t.Fatal("unexpected dependency")
	}
}

func TestFinalizedResultRetryIsIdempotent(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	j := assignment(t, c, s, n)
	submit(t, s, n, j)
	submit(t, s, n, j)
	if c.state.Model.Version != 1 || c.state.Nodes[n.NodeID].Verified != 1 {
		t.Fatal("finalized retry changed contribution")
	}
}
func TestPausedClientCannotTrain(t *testing.T) {
	co, s := testCo(t)
	_ = s
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cl, _ := newClient(ctx, t.TempDir())
	if e := cl.connect(encodeConfig(co.config)); e != nil {
		t.Fatal(e)
	}
	_ = co.startRound(100, 1, 60)
	cl.tick()
	cl.mu.Lock()
	defer cl.mu.Unlock()
	if cl.busy || cl.pending != nil || cl.progress > 0 {
		t.Fatal("client trained while paused")
	}
}
func TestClientPauseStopsRunningTask(t *testing.T) {
	co, s := testCo(t)
	_ = s
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cl, _ := newClient(ctx, t.TempDir())
	if e := cl.connect(encodeConfig(co.config)); e != nil {
		t.Fatal(e)
	}
	_ = cl.allow(1)
	_ = co.startRound(1200, 1, 60)
	cl.tick()
	time.Sleep(20 * time.Millisecond)
	cl.mu.Lock()
	running := cl.busy
	cl.mu.Unlock()
	if !running {
		t.Fatal("task did not start")
	}
	cl.pause()
	time.Sleep(50 * time.Millisecond)
	cl.mu.Lock()
	defer cl.mu.Unlock()
	if cl.busy || cl.pending != nil || cl.consent {
		t.Fatal("pause did not cancel and revoke")
	}
}
func TestCoordinatorLossStopsRunningTask(t *testing.T) {
	co, s := testCo(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	cl, _ := newClient(ctx, t.TempDir())
	if e := cl.connect(encodeConfig(co.config)); e != nil {
		t.Fatal(e)
	}
	_ = cl.allow(1)
	_ = co.startRound(1200, 1, 60)
	cl.tick()
	time.Sleep(20 * time.Millisecond)
	s.Close()
	cl.tick()
	time.Sleep(50 * time.Millisecond)
	cl.mu.Lock()
	defer cl.mu.Unlock()
	if cl.busy || cl.pending != nil {
		t.Fatal("training continued after network loss")
	}
}

func TestOldBuildCannotEnrollOverInternet(t *testing.T) {
	if !modernToolchain() {
		if e := checkNetworkBuildPolicy("https://example.org"); e == nil {
			t.Fatal("old build permitted Internet enrollment")
		}
		if e := checkListenBuildPolicy("0.0.0.0:18741"); e == nil {
			t.Fatal("old build permitted public binding")
		}
	}
	if e := checkNetworkBuildPolicy("http://127.0.0.1:18741"); e != nil {
		t.Fatal(e)
	}
}
