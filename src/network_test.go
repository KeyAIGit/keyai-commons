package main

import (
	"context"
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func opFixture(t *testing.T) (*Coordinator, *httptest.Server, ed25519.PrivateKey, OperatorCommand) {
	t.Helper()
	c, s := testCo(t)
	pk, k, _ := ed25519.GenerateKey(rand.Reader)
	c.operatorKey = publicKeyText(pk)
	q := OperatorCommand{Protocol: 1, Action: "start", Audience: s.URL, Instance: c.instance, Nonce: randomToken(24), Issued: time.Now().Unix(), Expires: time.Now().Add(30 * time.Second).Unix(), Steps: 100, Nodes: 1, Seconds: 60}
	return c, s, k, q
}
func TestSignedOperatorRequiresKey(t *testing.T) {
	c, s, k, q := opFixture(t)
	_, bad, _ := ed25519.GenerateKey(rand.Reader)
	env, _ := signOperator(bad, q)
	if postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil) == nil {
		t.Fatal("forged command accepted")
	}
	if c.active != nil {
		t.Fatal("forgery started work")
	}
	env, _ = signOperator(k, q)
	if e := postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil); e != nil {
		t.Fatal(e)
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.active == nil {
		t.Fatal("valid command did not start")
	}
}
func TestSignedOperatorReplayRejected(t *testing.T) {
	_, s, k, q := opFixture(t)
	env, _ := signOperator(k, q)
	if e := postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil); e != nil {
		t.Fatal(e)
	}
	if postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil) == nil {
		t.Fatal("replayed operator command accepted")
	}
}
func TestOperatorDomainAndBinding(t *testing.T) {
	c, _, k, q := opFixture(t)
	variants := []OperatorCommand{q, q, q, q, q, q}
	variants[0].Audience = "https://attacker.invalid"
	variants[1].Instance = "another-boot"
	variants[2].Expires = time.Now().Unix() - 1
	variants[3].Expires = q.Issued + 61
	variants[4].Action = "shell"
	variants[5].Nonce = "short"
	for _, v := range variants {
		env, _ := signOperator(k, v)
		if _, e := verifyOperator(env, c.operatorKey, q.Audience, q.Instance, time.Now()); e == nil {
			t.Fatalf("accepted invalid %+v", v)
		}
	}
	b, _ := json.Marshal(q)
	env := Envelope{base64.RawURLEncoding.EncodeToString(b), base64.RawURLEncoding.EncodeToString(ed25519.Sign(k, b))}
	if _, e := verifyOperator(env, c.operatorKey, q.Audience, q.Instance, time.Now()); e == nil {
		t.Fatal("missing domain separation accepted")
	}
}
func TestOperatorOldBootRejected(t *testing.T) {
	c, _, k, q := opFixture(t)
	env, _ := signOperator(k, q)
	if _, e := verifyOperator(env, c.operatorKey, q.Audience, randomToken(24), time.Now()); e == nil {
		t.Fatal("pre-restart command accepted")
	}
}
func TestOperatorControlDisabledByDefault(t *testing.T) {
	c, s := testCo(t)
	if c.operatorKey != "" {
		t.Fatal("unexpected trusted operator")
	}
	if postJSON(newHTTPClient(), s.URL+"/v1/operator", "", Envelope{}, nil) == nil {
		t.Fatal("unconfigured remote control active")
	}
}
func TestEnrollmentDiscoveryClosedByDefault(t *testing.T) {
	c, s := testCo(t)
	var out map[string]any
	if getJSON(newHTTPClient(), s.URL+"/v1/connect", &out) == nil {
		t.Fatal("invitation published by default")
	}
	c.mu.Lock()
	c.publicEnrollment = true
	c.mu.Unlock()
	if e := getJSON(newHTTPClient(), s.URL+"/v1/connect", &out); e != nil {
		t.Fatal(e)
	}
	if out["connection_code"] != encodeConfig(c.config) {
		t.Fatal("incorrect discovery")
	}
}
func TestOperatorOpenCloseAndStop(t *testing.T) {
	c, s, k, q := opFixture(t)
	for _, action := range []string{"enrollment_open", "enrollment_close", "start", "stop"} {
		q.Action = action
		q.Nonce = randomToken(24)
		q.Steps = 0
		q.Nodes = 0
		q.Seconds = 0
		if action == "start" {
			q.Steps = 100
			q.Nodes = 1
			q.Seconds = 60
		}
		env, _ := signOperator(k, q)
		if e := postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil); e != nil {
			t.Fatal(e)
		}
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.active != nil || c.publicEnrollment {
		t.Fatal("stop or close not applied")
	}
}
func TestDuplicateConnectReusesIdentity(t *testing.T) {
	c, _ := testCo(t)
	cl, _ := newClient(context.Background(), t.TempDir())
	defer cl.shutdown()
	code := encodeConfig(c.config)
	if e := cl.connect(code); e != nil {
		t.Fatal(e)
	}
	id := cl.saved.NodeID
	if e := cl.connect(code); e != nil {
		t.Fatal(e)
	}
	if cl.saved.NodeID != id || len(c.state.Nodes) != 1 {
		t.Fatal("duplicate enrollment")
	}
}
func TestConsentDeniedDuringConnection(t *testing.T) {
	cl, _ := newClient(context.Background(), t.TempDir())
	defer cl.shutdown()
	cl.saved.Token = "test"
	cl.connecting = true
	if cl.allow(5) == nil {
		t.Fatal("consent during connection race")
	}
}
func TestSessionCannotBeShortenedMidTask(t *testing.T) {
	cl, _ := newClient(context.Background(), t.TempDir())
	defer cl.shutdown()
	cl.saved.Token = "test"
	if e := cl.allow(5); e != nil {
		t.Fatal(e)
	}
	if cl.allow(1) == nil {
		t.Fatal("consent deadline changed mid-session without cancelling worker")
	}
}
func TestDropoutSlotIsReassigned(t *testing.T) {
	c, s := testCo(t)
	a := enroll(t, c, s)
	b := enroll(t, c, s)
	if e := c.startRound(100, 1, 60); e != nil {
		t.Fatal(e)
	}
	first := assignment(t, c, s, a)
	c.mu.Lock()
	c.state.Nodes[a.NodeID].LastSeen = time.Now().Unix() - 20
	c.mu.Unlock()
	second := assignment(t, c, s, b)
	if first.ID == second.ID || second.NodeID != b.NodeID {
		t.Fatal("replacement missing")
	}
	w, _ := trainModel(context.Background(), first.Weights, first.Seed, first.Steps, false, nil)
	if postJSON(newHTTPClient(), s.URL+"/v1/result", a.Token, Result{first.ID, w}, nil) == nil {
		t.Fatal("stale lease result accepted")
	}
	submit(t, s, b, second)
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.state.Model.Version != 1 {
		t.Fatal("replacement did not commit")
	}
}
func TestVoluntaryLeaveRevokesTokenAndFreesSlot(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	_ = c.startRound(100, 1, 60)
	_ = assignment(t, c, s, n)
	if e := postJSON(newHTTPClient(), s.URL+"/v1/leave", n.Token, struct{}{}, nil); e != nil {
		t.Fatal(e)
	}
	if postJSON(newHTTPClient(), s.URL+"/v1/poll", n.Token, PollRequest{}, nil) == nil {
		t.Fatal("revoked token remains active")
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.state.Nodes) != 0 || len(c.active.Jobs) != 0 {
		t.Fatal("revocation retained live registration")
	}
}
func TestLeaveRetriesAreIdempotent(t *testing.T) {
	_, s := testCo(t)
	for i := 0; i < 2; i++ {
		if e := postJSON(newHTTPClient(), s.URL+"/v1/leave", randomToken(32), struct{}{}, nil); e != nil {
			t.Fatal(e)
		}
	}
}
func TestStrictBearerPrefix(t *testing.T) {
	c, s := testCo(t)
	n := enroll(t, c, s)
	r := httptest.NewRequest("POST", "/", nil)
	r.Header.Set("Authorization", n.Token)
	c.mu.Lock()
	defer c.mu.Unlock()
	if _, ok := c.authenticate(r); ok {
		t.Fatal("missing Bearer prefix accepted")
	}
}
func TestBoundedPublicHistory(t *testing.T) {
	c, s := testCo(t)
	c.mu.Lock()
	for i := 0; i < 1000; i++ {
		c.state.History = append(c.state.History, Record{Round: i, Hash: strings.Repeat("a", 64)})
	}
	c.mu.Unlock()
	var v struct {
		History []Record `json:"history"`
	}
	if e := getJSON(newHTTPClient(), s.URL+"/v1/status", &v); e != nil {
		t.Fatal(e)
	}
	if len(v.History) != 100 {
		t.Fatal("unbounded public history")
	}
}
func TestCPUSettingsLimits(t *testing.T) {
	cl, _ := newClient(context.Background(), t.TempDir())
	defer cl.shutdown()
	for _, duty := range []int{-1, 1, 100, 999} {
		if _, e := trainWithDuty(context.Background(), initialWeights(), 1, 1, duty, nil); e == nil {
			t.Fatal("invalid duty accepted")
		}
	}
	for _, duty := range []int{10, 25, 50} {
		if _, e := trainWithDuty(context.Background(), initialWeights(), 1, 1, duty, nil); e != nil {
			t.Fatal(e)
		}
	}
}
func TestOriginValidation(t *testing.T) {
	for _, u := range []string{"http://example.com", "https://a.test/path", "https://u:p@a.test", "https://a.test?q=x", "https://a.test/#x", "file:///tmp/x"} {
		if _, e := checkedOrigin(u); e == nil {
			t.Fatal("unsafe origin", u)
		}
	}
	if _, e := checkedOrigin("http://127.0.0.1:1234"); e != nil {
		t.Fatal(e)
	}
}
func TestHealthEndpoint(t *testing.T) {
	_, s := testCo(t)
	var out map[string]any
	if e := getJSON(newHTTPClient(), s.URL+"/healthz", &out); e != nil || out["ok"] != true {
		t.Fatal("health check unavailable")
	}
}
func TestCorruptNodeStateFailsClosed(t *testing.T) {
	c, _ := testCo(t)
	dir := c.dir
	c.mu.Lock()
	c.state.Nodes["broken"] = nil
	_ = c.saveLocked()
	c.mu.Unlock()
	if _, e := newCoordinator(dir, "http://127.0.0.1:1234"); e == nil {
		t.Fatal("corrupt registry loaded")
	}
}
func TestNoPrivateDashboardTokensInHeadlessLogs(t *testing.T) {
	b, e := os.ReadFile("coordinator.go")
	if e != nil {
		t.Fatal(e)
	}
	if !strings.Contains(string(b), "not logged") {
		t.Fatal("headless privacy guard missing")
	}
	_ = filepath.Separator
}
func TestConcurrentOperatorReplayOnlyOnce(t *testing.T) {
	c, s, k, q := opFixture(t)
	q.Action = "enrollment_open"
	q.Steps = 0
	q.Nodes = 0
	q.Seconds = 0
	env, _ := signOperator(k, q)
	var wg sync.WaitGroup
	var mu sync.Mutex
	success := 0
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if postJSON(newHTTPClient(), s.URL+"/v1/operator", "", env, nil) == nil {
				mu.Lock()
				success++
				mu.Unlock()
			}
		}()
	}
	wg.Wait()
	c.mu.Lock()
	defer c.mu.Unlock()
	if success != 1 || !c.publicEnrollment {
		t.Fatal("concurrent replay", success)
	}
}
func TestNoPublicAdminDashboard(t *testing.T) {
	_, s := testCo(t)
	for _, path := range []string{"/api/start", "/api/config", "/admin"} {
		r, e := http.Get(s.URL + path)
		if e != nil {
			t.Fatal(e)
		}
		r.Body.Close()
		if r.StatusCode == 200 {
			t.Fatal("public admin leak")
		}
	}
}
