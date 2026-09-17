package main

import (
	"fmt"
	"net"
	"net/url"
	"runtime"
	"strings"
)

// The provided container toolchain may be older than the current security
// baseline. Such binaries are intentionally confined to loopback testing.
// Rebuild with a reviewed, supported toolchain for any Internet deployment.
func modernToolchain() bool {
	var major, minor, patch int
	_, _ = fmt.Sscanf(runtime.Version(), "go%d.%d.%d", &major, &minor, &patch)
	return major > 1 || (major == 1 && (minor > 27 || (minor == 27 && patch >= 1)))
}
func isLoopbackOrigin(raw string) bool {
	u, e := url.Parse(raw)
	if e != nil {
		return false
	}
	ip := net.ParseIP(u.Hostname())
	return u.Hostname() == "localhost" || (ip != nil && ip.IsLoopback())
}
func checkNetworkBuildPolicy(raw string) error {
	if !modernToolchain() && !isLoopbackOrigin(raw) {
		return fmt.Errorf("this %s development build is LOCAL-TEST ONLY; Internet connections require a reviewed rebuild with Go 1.27.1 or newer", runtime.Version())
	}
	return nil
}
func checkListenBuildPolicy(addr string) error {
	if modernToolchain() {
		return nil
	}
	host, _, e := net.SplitHostPort(addr)
	ip := net.ParseIP(strings.Trim(host, "[]"))
	if e != nil || ip == nil || !ip.IsLoopback() {
		return fmt.Errorf("this %s development build may bind only a loopback address; rebuild before public hosting", runtime.Version())
	}
	return nil
}
