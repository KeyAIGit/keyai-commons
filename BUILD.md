# Build and verification

No external Go packages are required. Download the compiler only from an official
source, verify its published checksum, and review the supported security release.
This source accepts Internet mode only when compiled with Go 1.27.1 or newer.
Do not remove that check to expose an older development binary to the Internet.

```
cd src
go version
go test -race -v ./...
go vet ./...
go build -trimpath -ldflags="-s -w" -o ../keyai-commons .
```

Windows without a C compiler can run `go test -v ./...`; race detection needs the
appropriate C toolchain. Linux race tests are recorded separately in test-results.txt.

Cross-compile examples from a shell with a reviewed compiler:
```
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags="-s -w" -o ../KeyAI-Commons.exe .
CGO_ENABLED=0 GOOS=darwin GOARCH=arm64 go build -trimpath -ldflags="-s -w" -o ../keyai-commons-macos .
```

`python package.py` creates client archives and a source/site package. The environment
variable `GO_BINARY` can select an explicit compiler. It refuses to label an outdated
compiler build as Internet-ready. It never includes a user's configuration directory.

Integration tests use three separate native processes on one Linux host:
`python integration_test.py`. They are not evidence of three physical devices.
The synthetic initial/final loss and actual observed cancellation time are in
`integration-results.json`.

`render_preview.py` renders the shipped layout without scripts or network access.
`browser-results.json` explicitly distinguishes layout checks from live browser E2E.
`browser_test.py` is included for a workstation where browser loopback navigation
is permitted; it was blocked by the managed browser policy in the build environment.
