# KeyAI Commons

[![CI](https://github.com/KeyAIGit/keyai-commons/actions/workflows/ci.yml/badge.svg)](https://github.com/KeyAIGit/keyai-commons/actions/workflows/ci.yml) · [Русский](README_RU.md) · [Roadmap](ROADMAP.md) · [Releases](https://github.com/KeyAIGit/keyai-commons/releases)

**Volunteer computing for shared AI research. Your computer, your permission, your stop button.**

An open-source, operator-controlled distributed-training engineering pilot. A participant explicitly enables a time-limited session; the organizer separately starts a signed training round. Both are required. Closing a browser tab alone does not stop the client: use **Pause now** or **Exit application**.

> **Current scope:** a real 65-parameter CPU neural network on synthetic data. Not an LLM, not a GPU training system, not a public production network. No financial rewards, equity or guaranteed future inference rights. No public coordinator is deployed.

## Try the local demo

Download a **LOCAL-TEST** package from [Releases](https://github.com/KeyAIGit/keyai-commons/releases), extract it, and run `LOCAL-DEMO.cmd` on Windows or `./local-demo.sh` on Linux/macOS. These unsigned development binaries deliberately refuse Internet participation. Review the source and do not disable your operating system's security protections.

From source, install Go and run `BUILD-AND-DEMO.cmd` on Windows. On Linux/macOS: `cd src && go test ./... && go build -trimpath -o ../keyai-commons . && cd .. && ./keyai-commons demo`. Older Go builds are loopback-only; Internet-mode source builds require Go 1.27.1+ and a separate security review. A current compiler alone does not make a release safe for public deployment.

In the client, acknowledge the consent checkbox and click **Enable participation**. In the operator dashboard, click **Start round**. **Pause now** stops participation locally. Launching the app never starts training or grants consent by itself.

## Implemented and intentionally limited

Signed bounded jobs; enrollment; revocable session consent; fixed CPU training; full reference replay; model averaging; saved checkpoints; dropout deadlines; separate authenticated loopback operator UI. No remote shell, arbitrary downloaded code, silent updates or OS autostart. No strong OS sandbox is claimed. Reference replay repeats the work, so this pilot does **not** demonstrate compute savings or scalable proof of computation.

See [Architecture](ARCHITECTURE.md), [Build](BUILD.md), [Security](SECURITY.md), [Privacy](PRIVACY.md) and [Deployment gates](DEPLOY.md). Initial reports in `test-results.txt`, `integration-results.json`, `browser-results.json` and `BUILD_REPORT.json` are historical single-host development evidence, not independent audits or results for every later commit. The CI badge reports the current branch separately.

## Build this with us

Use [Issues](https://github.com/KeyAIGit/keyai-commons/issues) to propose work and pull requests to submit changes. Start with [CONTRIBUTING.md](CONTRIBUTING.md) and [ROADMAP.md](ROADMAP.md). Preserve participant control and publish reproducible evidence, not download-count promises. MIT licensed; see [LICENSE](LICENSE).
