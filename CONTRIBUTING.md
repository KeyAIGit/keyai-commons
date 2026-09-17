# Contributing

Discuss substantial changes in an issue before opening a pull request. Small documentation fixes can go straight to a PR. English and Russian contributions are welcome.

## Local checks

From `src`: run `go test -count=1 ./...`, `go vet ./...` and, where a C toolchain is available, `go test -race ./...`. Build to the repository root with `go build -trimpath -o ../keyai-commons .`; on Linux, run `python3 integration_test.py` from the root. Python's standard library is sufficient for that integration test. Browser preview scripts are optional and have separate dependencies.

## Non-negotiable participant controls

- No work without explicit participant consent and an operator command.
- Consent must be revocable and expire; restart must never restore it silently.
- No arbitrary remote shell, downloaded plugins, crypto mining or hidden autostart.
- Private node credentials, state, invite codes and operator session URLs must never enter commits, screenshots or issue attachments.
- Keep the public API separate from the private operator UI.

## Pull requests

Describe the behavior changed, reproduction commands, tests, resource/network impact and known limitations. Add a regression test for bug fixes. Keep unrelated refactors separate. Do not present several local processes as several physical hosts or synthetic learning as useful LLM training.

CI runs on pushes and pull requests with read-only repository permissions. Maintainers review changes before merging. Never execute code from untrusted PRs with production secrets.

## Security reports

Read SECURITY.md. Report sensitive vulnerabilities through the repository's private vulnerability reporting feature when available, not a public issue containing an exploit or credentials. Public issues may document non-sensitive hardening work.

Contributions are provided under the repository's existing MIT license. Please contribute only material you are authorized to share.
