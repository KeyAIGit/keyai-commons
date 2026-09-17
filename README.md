# KeyAI Commons

**Community first. Computing later.** An open research project designing a safe, useful and eventually decentralized AI training network on voluntary computers.

[Website](https://keyaigit.github.io/keyai-commons/) · [Discussions](https://github.com/KeyAIGit/keyai-commons/discussions) · [Architecture](docs/foundation/ARCHITECTURE.md) · [Русский](docs/foundation/README_RU.md) · [Governance](GOVERNANCE.md)

## What to do now

Join the discussion, review the architecture, propose experiments, improve accessibility or help with security review. **No worker installation or training permission is needed to join.** We are not claiming a production decentralized network, a useful language model, guaranteed compute savings, millions of active devices, ownership shares or payouts.

The public site is white, readable, bilingual and explicitly distinguishes today's community from future computing. Its globe is illustrative, not live telemetry. The notification is a UI demonstration, not an OS notification or a training launch.

## Separate community application

`src/cmd/community` is a separate build target with **no trainer, coordinator connection, task downloader, automatic update or autostart**. It can record and clear an interest preference on the local computer and explain the project. It does not register a device or subscribe the user to notifications. The application and the website share the new accessible visual style.

Developer build (Go 1.27.1 recommended):

```sh
cd src
go test -race ./cmd/community
go build -trimpath -o ../keyai-community ./cmd/community
cd ..
./keyai-community
```

On Windows name the output `KeyAI-Community.exe`. The local browser interface is token-protected and listens only on 127.0.0.1. Closing the tab does not terminate the local service; use Exit application. No network training can run in this target. A future computing capability would be a separately reviewed and explicitly authorized product change, not silent activation of this preview.

## Legacy developer experiment

Earlier v0.2 releases and the root `src` command implement a tiny synthetic 65-parameter CPU training experiment. They remain development/reproducibility artifacts, **not today's recommended public participation app**. The existing temporary coordinator is not a permanent decentralized backend. Do not mistake old downloadable EXEs for the new community target or tell users to bypass OS warnings.

The root tests and local demo remain available for researchers. These do not establish GPU/LLM training, economical Internet-scale optimization or independent security certification. Full reference replay duplicates compute.

## Architecture and distribution gates

Read [the technical architecture](docs/foundation/ARCHITECTURE.md) for dataset manifests, compatible GPU cohorts, failure recovery, standing consent, decentralization targets and acceptance gates. TensorFlow Federated, Hivemind, Flower and DiLoCo are assessed as references/candidates, not integrated production dependencies in this preview.

[Store plan](docs/foundation/STORE_PLAN.md) documents the free Microsoft onboarding route, genuine Private audience testing, identity requirements and remaining Mac/Linux work. No Store listing, verified publisher, signed installer or macOS notarization is implied by preparation files. `packaging/windows/build_msix.py` never signs, installs or submits a package.

[Privacy](docs/foundation/PRIVACY.md), [maintainers](MAINTAINERS.md), [contribution rules](CONTRIBUTING.md). MIT covers this repository's source; future data and model licenses require their own review. A maintainer merge, campaign approval and device permission are separate decisions.
