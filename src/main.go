package main

import (
	"context"
	"embed"
	"flag"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"runtime"
	"syscall"
)

//go:embed web/*.html
var assets embed.FS

func serveAsset(w http.ResponseWriter, name string) {
	b, e := assets.ReadFile("web/" + name)
	if e != nil {
		http.Error(w, "missing embedded interface", 500)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	_, _ = w.Write(b)
}
func openBrowser(url string) {
	// Local browser launch only. No endpoint ever accepts commands or arguments
	// for this function; URLs are generated from a loopback listener and token.
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	if e := cmd.Start(); e == nil {
		go func() { _ = cmd.Wait() }()
	}
}
func defaultDir(role string) string {
	d, e := os.UserConfigDir()
	if e != nil {
		d = "."
	}
	return filepath.Join(d, "KeyAICommons", role)
}
func main() {
	if len(os.Args) > 1 && os.Args[1] == "operator" {
		if e := operatorMain(os.Args[2:]); e != nil {
			fatal(e)
		}
		return
	}
	if len(os.Args) > 1 && (os.Args[1] == "version" || os.Args[1] == "--version") {
		fmt.Printf("KeyAI Commons %s | %s | %s/%s\n", version, runtime.Version(), runtime.GOOS, runtime.GOARCH)
		return
	}
	runtime.GOMAXPROCS(2)
	mode := "client"
	args := os.Args[1:]
	if len(args) > 0 && (args[0] == "client" || args[0] == "coordinator" || args[0] == "demo") {
		mode = args[0]
		args = args[1:]
	}
	fs := flag.NewFlagSet("KeyAI Commons "+mode, flag.ExitOnError)
	dir := fs.String("data", defaultDir(mode), "private local state directory")
	listen := fs.String("listen", "127.0.0.1:18741", "coordinator public API listen address")
	publicURL := fs.String("public-url", "", "public HTTPS origin; loopback HTTP allowed for local testing")
	operatorKey := fs.String("operator-key", "", "optional Ed25519 public key for signed remote commands")
	persistence := fs.String("persistence", "local-disk", "local-disk or ephemeral; describes host storage")
	noBrowser := fs.Bool("no-browser", false, "print local dashboard URL without opening a browser")
	_ = fs.Parse(args)
	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()
	switch mode {
	case "client":
		c, cleanup, e := runClient(ctx, *dir, *noBrowser)
		if e != nil {
			fatal(e)
		}
		defer cleanup()
		<-c.done.Done()
	case "coordinator":
		_, cleanup, e := runCoordinatorWithOptions(ctx, *dir, *listen, *publicURL, *noBrowser, CoordinatorOptions{*operatorKey, *persistence})
		if e != nil {
			fatal(e)
		}
		defer cleanup()
		<-ctx.Done()
	case "demo":
		// Starts two local HTTP services, but NEVER starts training or gives consent.
		co, stopCo, e := runCoordinator(ctx, filepath.Join(*dir, "coordinator"), "127.0.0.1:0", "", *noBrowser)
		if e != nil {
			fatal(e)
		}
		defer stopCo()
		cl, stopCl, e := runClient(ctx, filepath.Join(*dir, "participant"), *noBrowser)
		if e != nil {
			fatal(e)
		}
		defer stopCl()
		if cl.saved.Token == "" || cl.saved.Config.URL != co.config.URL {
			if e = cl.connect(encodeConfig(co.config)); e != nil {
				fatal(e)
			}
		}
		fmt.Println("LOCAL DEMO ONLY. Enable participation in the client, then press Start round in the operator dashboard.")
		<-cl.done.Done()
	}
}
func fatal(e error) { fmt.Fprintln(os.Stderr, "KeyAI Commons:", e); os.Exit(1) }
