# Governance: three independent decisions

**Anyone can propose code. Maintainers choose official releases. Participants choose what runs on their computers.** Joining the community, merging a pull request and approving a campaign are not interchangeable permissions.

The founding maintainer and repository owner is Bekzod, GitHub **@KeyAIGit**. This is the actual initial authority, not decentralized governance. MIT allows independent forks but grants no control over the official clients, no ownership share and no claim on donated computing resources.

Discuss major changes in an issue. Submit changes on a branch through a pull request. Required checks test behavior; they do not prove security. The maintainer reviews the diff and evidence and records acceptance, revision or rejection. AI assistance acts under the owner's authority; it is not independent review. No unattended merging, production secrets in contributor workflows, remote code loading, or hidden consent changes.

Repository policy: pull requests, passing Windows/Linux/macOS checks, resolved review conversations, and blocked force pushes/deletion for main. One human maintainer means zero independently required approvals until another trusted maintainer is appointed; do not misrepresent this as two-person review. See actual GitHub branch settings for enforcement, because a policy file alone does not configure protections. An owner can change those settings.

Before admitting a second person with write rights, record their scope and reason in a public governance discussion and MAINTAINERS.md. Require independent approval for training, protocol, privacy, authorization and signing changes once independent reviewers really exist. Computing contributions and popularity never automatically confer repository or campaign authority.

Future decentralized campaign authority must have multiple independent operators, specified trust roots, revocation and conflict handling. Until those exist, label experiments founder-operated. A campaign's approved model/data/workload and resource limits must match the participant's local standing policy. Broadening them requires renewed consent. The Community Preview has no campaign-consent or execution feature.

Security reports belong in GitHub private vulnerability reporting when available. Never publish credentials, private dashboard URLs or personal datasets. Respectful dissent can be documented in the original issue; forking remains available under the MIT license.
