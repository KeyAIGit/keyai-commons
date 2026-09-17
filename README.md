# KeyAI Commons

[![CI](https://github.com/KeyAIGit/keyai-commons/actions/workflows/ci.yml/badge.svg)](https://github.com/KeyAIGit/keyai-commons/actions/workflows/ci.yml) · [Русский](README_RU.md) · [Website](https://keyaigit.github.io/keyai-commons/) · [Downloads](https://github.com/KeyAIGit/keyai-commons/releases) · [Roadmap](ROADMAP.md)

**Volunteer computing for shared AI research. Your computer, your permission, your stop button.**

## Download the v0.2.0 research preview

Portable Windows x64/ARM64, Linux x64/ARM64, and macOS Intel/Apple Silicon packages are published in [Releases](https://github.com/KeyAIGit/keyai-commons/releases/tag/v0.2.0-pilot.1). Participants do not need Go or Python. Extract completely, read START-HERE.txt, then open START-CLIENT.cmd on Windows or ./start-client.sh on Linux/macOS. LOCAL-DEMO runs a separate local experiment.

**Unsigned development builds.** Do not disable OS security protections. macOS builds are not notarized. No independent security audit is claimed.

An organizer provides an HTTPS coordinator address or a pinned connection code. Enter it in the client, review the network identity, choose CPU pacing and enable a short session. The organizer must separately start a signed round. Neither launching the app nor connecting it grants training permission. Closing a browser tab does not stop the application: use **Pause now** or **Exit application**.

> **Actual scope:** a 65-parameter CPU network learning synthetic data, not an LLM, GPU network or ASI. No financial rewards, equity or guaranteed future inference access. 256 registrations, 32 participants per round. Full reference replay duplicates compute; no efficiency or million-node claim is made.

## New in 0.2.0

- Portable modern-toolchain builds; explicit HTTPS discovery; CPU pacing choices; participant-controlled registration revocation.
- Optional signed remote operator commands with origin/instance binding, expiry and replay prevention. Private keys remain on the organizer's computer. No remote shell or downloaded code.
- Abandoned task-slot reassignment, bounded retries, duplicate-registration prevention, constant-time token hash comparison where used, indexed authentication, bounded public history and cached validation metrics.
- A public status/download website, non-root Docker deployment, persistent-volume Compose template and documented ephemeral-host limitations.

The local operator dashboard is still authenticated and loopback-only. Public remote control is disabled unless an operator public key is explicitly configured. Server restart never resumes a round or automatically opens public enrollment.

## Hosting and testing

See [deploy/README.md](deploy/README.md) for HTTPS deployment and signed operator commands. A static website is not a coordinator. A free host using ephemeral storage can lose registration and checkpoint state when restarted; participants must explicitly reconnect. Such a host is an invited experiment, not a durable public service.

Build from source with Go 1.27.1+: `cd src && go test ./... && go build -trimpath -o ../keyai-commons .`. Older development builds remain loopback-only. Packaging: `python scripts/package_release.py`. Binary distributions have no Python dependency.

Tests: `cd src && go test -race -count=1 ./... && go vet ./...`. `python integration_test.py` exercises several participant processes; `python browser_test.py` exercises actual browser controls when Playwright/Chromium are installed. Test scope and host count must always be reported. Historical reports are not evidence for a later revision.

## Collaborate

Use [Issues](https://github.com/KeyAIGit/keyai-commons/issues), [Discussions](https://github.com/KeyAIGit/keyai-commons/discussions) and pull requests. Read [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) and [PRIVACY.md](PRIVACY.md). Preserve participant control. Publish measured results rather than promises based on downloads. MIT licensed.
