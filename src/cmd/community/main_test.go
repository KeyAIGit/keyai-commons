package main

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func testApp(t *testing.T) *app {
	t.Helper()
	a, err := newApp(t.TempDir(), "127.0.0.1:12345", func() {})
	if err != nil {
		t.Fatal(err)
	}
	return a
}
func call(a *app, method, path, body, origin, token string) *httptest.ResponseRecorder {
	r := httptest.NewRequest(method, "http://"+a.host+path, strings.NewReader(body))
	r.Header.Set("Content-Type", "application/json")
	r.Header.Set("X-Session-Token", token)
	if origin != "" {
		r.Header.Set("Origin", origin)
	}
	w := httptest.NewRecorder()
	a.handler().ServeHTTP(w, r)
	return w
}
func TestCommunityCannotTrain(t *testing.T) {
	a := testApp(t)
	for _, path := range []string{"/api/consent", "/api/start", "/api/connect", "/api/discover", "/v1/join", "/v1/poll", "/v1/result", "/v1/operator"} {
		if w := call(a, "POST", path, "{}", "", a.token); w.Code != 404 {
			t.Fatal(path, w.Code)
		}
	}
}
func TestDefaultNoPermission(t *testing.T) {
	a := testApp(t)
	w := call(a, "GET", "/api/status", "", "", a.token)
	var s map[string]any
	json.Unmarshal(w.Body.Bytes(), &s)
	if s["training_enabled"] != false || s["campaign_consent"] != false || s["registered"] != false || s["interested"] != false {
		t.Fatal(s)
	}
}
func TestInterestIsNotPermission(t *testing.T) {
	a := testApp(t)
	if w := call(a, "POST", "/api/preference", `{"interested":true}`, "", a.token); w.Code != 200 {
		t.Fatal(w.Body.String())
	}
	w := call(a, "GET", "/api/status", "", "", a.token)
	if !bytes.Contains(w.Body.Bytes(), []byte(`"interested":true`)) || !bytes.Contains(w.Body.Bytes(), []byte(`"training_enabled":false`)) {
		t.Fatal(w.Body.String())
	}
}
func TestInterestPersistsWithoutConsent(t *testing.T) {
	a := testApp(t)
	if err := a.save(true); err != nil {
		t.Fatal(err)
	}
	b, err := newApp(a.dir, a.host, func() {})
	if err != nil || !b.interested {
		t.Fatal(err)
	}
	if a.token == b.token {
		t.Fatal("session must rotate")
	}
	if w := call(b, "GET", "/api/status", "", "", b.token); !bytes.Contains(w.Body.Bytes(), []byte(`"campaign_consent":false`)) {
		t.Fatal(w.Body.String())
	}
}
func TestClearRemovesPreference(t *testing.T) {
	a := testApp(t)
	a.save(true)
	if w := call(a, "POST", "/api/reset", "{}", "", a.token); w.Code != 200 {
		t.Fatal(w.Code)
	}
	if _, err := os.Stat(filepath.Join(a.dir, "community-preference.json")); !os.IsNotExist(err) {
		t.Fatal(err)
	}
	if a.interested {
		t.Fatal("not cleared")
	}
}
func TestTokenRequired(t *testing.T) {
	a := testApp(t)
	for _, key := range []string{"", "wrong"} {
		if w := call(a, "POST", "/api/preference", `{"interested":true}`, "", key); w.Code != 403 {
			t.Fatal(w.Code)
		}
	}
}
func TestCrossOriginRejected(t *testing.T) {
	a := testApp(t)
	if w := call(a, "POST", "/api/preference", `{"interested":true}`, "https://example.org", a.token); w.Code != 403 {
		t.Fatal(w.Code)
	}
}
func TestWrongHostRejected(t *testing.T) {
	a := testApp(t)
	r := httptest.NewRequest("GET", "http://evil.example/", nil)
	w := httptest.NewRecorder()
	a.handler().ServeHTTP(w, r)
	if w.Code != 403 {
		t.Fatal(w.Code)
	}
}
func TestStrictPreferencePayload(t *testing.T) {
	a := testApp(t)
	for _, body := range []string{`{}`, `{"interested":true,"training":true}`, `{"interested":"yes"}`, `{"interested":true} {}`, strings.Repeat("a", 6000)} {
		if w := call(a, "POST", "/api/preference", body, "", a.token); w.Code != 400 {
			t.Fatal(body, w.Code)
		}
	}
}
func TestNoMutationByGet(t *testing.T) {
	a := testApp(t)
	for _, path := range []string{"/api/preference", "/api/reset", "/api/exit"} {
		if w := call(a, http.MethodGet, path, "{}", "", a.token); w.Code != 405 {
			t.Fatal(path, w.Code)
		}
	}
}
func TestExitCancelsLocalServer(t *testing.T) {
	a := testApp(t)
	ctx, cancel := context.WithCancel(context.Background())
	a.stop = cancel
	if w := call(a, "POST", "/api/exit", "{}", "", a.token); w.Code != 200 {
		t.Fatal(w.Code)
	}
	select {
	case <-ctx.Done():
	default:
		t.Fatal("no shutdown")
	}
}
func TestUIAndSecurityHeaders(t *testing.T) {
	a := testApp(t)
	w := call(a, "GET", "/", "", "", "")
	if w.Code != 200 || !strings.Contains(w.Body.String(), "Community preview") {
		t.Fatal(w.Code)
	}
	if w.Header().Get("X-Frame-Options") != "DENY" || !strings.Contains(w.Header().Get("Content-Security-Policy"), "connect-src 'self'") {
		t.Fatal(w.Header())
	}
}
