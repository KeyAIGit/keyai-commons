// KeyAI Commons Community Preview intentionally links no training implementation.
package main

import (
	"context"
	"crypto/rand"
	"crypto/subtle"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"sync"
	"syscall"
	"time"
)

//go:embed web/index.html
var assets embed.FS

const communityVersion = "0.4.0-community-preview"

type preference struct {
	Interested bool `json:"interested"`
}
type app struct {
	mu               sync.Mutex
	interested       bool
	dir, host, token string
	stop             context.CancelFunc
}

func newApp(dir, host string, stop context.CancelFunc) (*app, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return nil, err
	}
	a := &app{dir: dir, host: host, token: hex.EncodeToString(b), stop: stop}
	if err := os.MkdirAll(dir, 0700); err != nil {
		return nil, err
	}
	raw, err := os.ReadFile(filepath.Join(dir, "community-preference.json"))
	if err == nil {
		var p preference
		if len(raw) > 1024 {
			return nil, errors.New("local preference too large")
		}
		if err = json.Unmarshal(raw, &p); err != nil {
			return nil, errors.New("local preference is invalid")
		}
		a.interested = p.Interested
	} else if !os.IsNotExist(err) {
		return nil, err
	}
	return a, nil
}
func reply(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}
func fail(w http.ResponseWriter, code int, msg string) {
	reply(w, code, map[string]string{"error": msg})
}
func decode(w http.ResponseWriter, r *http.Request, v any) error {
	if r.Header.Get("Content-Type") != "application/json" {
		return errors.New("JSON required")
	}
	r.Body = http.MaxBytesReader(w, r.Body, 4096)
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return err
	}
	if err := dec.Decode(new(any)); err != io.EOF {
		return errors.New("extra JSON")
	}
	return nil
}
func (a *app) save(value bool) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	raw, err := json.Marshal(preference{value})
	if err != nil {
		return err
	}
	f, err := os.CreateTemp(a.dir, ".preference-*")
	if err != nil {
		return err
	}
	name := f.Name()
	defer os.Remove(name)
	if err = f.Chmod(0600); err != nil {
		f.Close()
		return err
	}
	if _, err = f.Write(raw); err != nil {
		f.Close()
		return err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return err
	}
	if err = f.Close(); err != nil {
		return err
	}
	if err = os.Rename(name, filepath.Join(a.dir, "community-preference.json")); err != nil {
		return err
	}
	a.interested = value
	return nil
}
func (a *app) handler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
		if r.Host != a.host {
			fail(w, 403, "Local host required")
			return
		}
		if r.URL.Path == "/" && r.Method == http.MethodGet {
			body, _ := assets.ReadFile("web/index.html")
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write(body)
			return
		}
		if r.URL.Path != "/api/status" && r.URL.Path != "/api/preference" && r.URL.Path != "/api/reset" && r.URL.Path != "/api/exit" {
			fail(w, 404, "No such feature in the community preview")
			return
		}
		if subtle.ConstantTimeCompare([]byte(r.Header.Get("X-Session-Token")), []byte(a.token)) != 1 {
			fail(w, 403, "Local session required")
			return
		}
		if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+a.host {
			fail(w, 403, "Cross-origin request refused")
			return
		}
		if r.URL.Path == "/api/status" {
			if r.Method != http.MethodGet {
				fail(w, 405, "GET required")
				return
			}
			a.mu.Lock()
			p := a.interested
			a.mu.Unlock()
			reply(w, 200, map[string]any{"version": communityVersion, "interested": p, "training_enabled": false, "registered": false, "preference_scope": "local_only", "campaign_consent": false})
			return
		}
		if r.Method != http.MethodPost {
			fail(w, 405, "POST required")
			return
		}
		if r.URL.Path == "/api/preference" {
			var p struct {
				Interested *bool `json:"interested"`
			}
			if decode(w, r, &p) != nil || p.Interested == nil {
				fail(w, 400, "Only an interested boolean is accepted")
				return
			}
			if a.save(*p.Interested) != nil {
				fail(w, 500, "Local preference could not be saved")
				return
			}
			reply(w, 200, map[string]bool{"saved": true})
			return
		}
		var empty struct{}
		if decode(w, r, &empty) != nil {
			fail(w, 400, "Empty JSON object required")
			return
		}
		if r.URL.Path == "/api/reset" {
			a.mu.Lock()
			err := os.Remove(filepath.Join(a.dir, "community-preference.json"))
			if err == nil || os.IsNotExist(err) {
				a.interested = false
			}
			a.mu.Unlock()
			if err != nil && !os.IsNotExist(err) {
				fail(w, 500, "Could not remove local preference")
				return
			}
			reply(w, 200, map[string]bool{"cleared": true})
			return
		}
		reply(w, 200, map[string]bool{"closed": true})
		a.stop()
	})
}
func browser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	if cmd.Start() == nil {
		go func() { _ = cmd.Wait() }()
	}
}
func run() error {
	if len(os.Args) == 2 && (os.Args[1] == "version" || os.Args[1] == "--version") {
		fmt.Println("KeyAI Commons", communityVersion, "| community only | no trainer")
		return nil
	}
	base, err := os.UserConfigDir()
	if err != nil {
		return err
	}
	dir := flag.String("data", filepath.Join(base, "KeyAICommons", "community"), "local preferences only")
	noBrowser := flag.Bool("no-browser", false, "do not open the local UI automatically")
	flag.Parse()
	if flag.NArg() != 0 {
		return errors.New("this community build has no client, coordinator, demo or training modes")
	}
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return err
	}
	defer listener.Close()
	a, err := newApp(*dir, listener.Addr().String(), cancel)
	if err != nil {
		return err
	}
	server := &http.Server{Handler: a.handler(), ReadHeaderTimeout: 4 * time.Second, ReadTimeout: 6 * time.Second, WriteTimeout: 6 * time.Second, IdleTimeout: 20 * time.Second, MaxHeaderBytes: 8192}
	failures := make(chan error, 1)
	go func() { failures <- server.Serve(listener) }()
	url := "http://" + a.host + "/#" + a.token
	raw, _ := json.Marshal(map[string]string{"ui_url": url})
	session := filepath.Join(*dir, "community-session-private.json")
	if err = os.WriteFile(session, raw, 0600); err != nil {
		server.Close()
		return err
	}
	defer os.Remove(session)
	fmt.Println("Community preview. Local preferences only. No training capability.")
	fmt.Println("Local UI:", url)
	if !*noBrowser {
		browser(url)
	}
	select {
	case <-ctx.Done():
	case err = <-failures:
		if !errors.Is(err, http.ErrServerClosed) {
			return err
		}
	}
	shutdownCtx, done := context.WithTimeout(context.Background(), 3*time.Second)
	defer done()
	return server.Shutdown(shutdownCtx)
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "KeyAI Commons:", err)
		os.Exit(1)
	}
}
