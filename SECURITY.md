# Security and launch gates

This is an experimental volunteer-compute client, not an independently audited product.

## Implemented boundaries

- No arbitrary workload code, shell, mining task, plugin or package download.
- A single fixed synthetic MLP workload; bounded shape, values, batches and lifetime.
- Explicit, revocable, nonpersistent session consent; no OS autorun or silent updates.
- Ed25519-signed job envelopes pinned to the invited network key and assigned node.
- HTTPS for remote enrollment; redirects refused; loopback HTTP for local testing only.
- Old toolchain builds refuse non-loopback enrollment/binding.
- A separate loopback admin listener with random token, Host and Origin checks.
- API body limits, server deadlines and limited concurrent reference verifications.
- Random node credentials stored hashed by the coordinator; no credentials in release ZIPs.
- Numeric, shape, hash and deterministic reference checks on submitted updates.

## Remaining risks / what not to claim

- A malicious operator could distribute a modified installer; inspect source and signatures.
- Jobs are signed, but signing does not prove that every program dependency is harmless.
- Native binary/runtime vulnerabilities remain possible. No strong OS sandbox is implemented.
- Best-effort pacing is not a hardware-enforced CPU, power or temperature limit.
- Clients have pseudonymous identities; one person can create multiple identities.
- Reference replay doubles work. It is not scalable proof-of-compute or Byzantine consensus.
- The small coordinator has no production DDoS protection, HA, durable audit ledger,
  cloud secret manager, key rotation UI, cross-host load testing or automatic backups.
- No independent privacy, licensing, legal-ownership or software security review is complete.
- Windows publisher signing and macOS notarization are absent. Do not disable OS protection.
- No multi-writer data directory support. Run only one process for each data directory.

Before an Internet pilot: rebuild with a reviewed supported Go release, independently
review the code, sign distributions, deploy a real TLS endpoint, restrict initial
admission, set up backups/monitoring, and test at least three separate physical hosts
on different networks including pause, shutdown, failed upload and coordinator restart.

Windows SmartScreen reference:
https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/
Go security guidance:
https://go.dev/doc/security/

## Private vulnerability reports

Use GitHub private vulnerability reporting under the repository Security tab. Do not put credentials, private state or sensitive exploit details in public issues. No guaranteed response time or paid bug bounty is offered.
