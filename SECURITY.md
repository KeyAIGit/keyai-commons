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

## Version 0.2.0 network-preview additions

Remote control is optional and disabled without an operator public key. Commands are signed using a distinct Ed25519 domain; bind to the HTTPS origin and a random server-boot identifier; expire in at most 60 seconds; and reject repeated nonces. Allowed actions are start, stop, finalize and enrollment open/close only. This is not arbitrary remote execution. A signature authenticates the organizer, not the mathematical correctness of a result.

HTTPS discovery is explicit trust-on-first-use at the address entered by the participant; the discovered task signing key is then pinned. The client does not silently replace a pin during polling. A host using ephemeral storage can lose its task identity at restart; re-enrollment must be explicit. Operator private keys must never be stored on a public host or in source control.

The network server is still a small pilot with full result replay and bounded admission. It is not Sybil-resistant or independently audited. Pacing a worker is not strong OS sandboxing, a temperature control or a hardware power cap. The desktop client has ordinary user-process privileges and no remote-code capability; a vulnerability could still affect the user's account. Do not run it as administrator.

Headless service startup no longer prints private dashboard/session tokens. Host application logs and private state still require proper access controls. A remote stop reaches clients on their next completed poll; network timeouts and the 30-second local deadline bound failures. Local pause cancels the local worker directly. A result already in transit may reach the server after pause; revoking participation does not retroactively erase a committed aggregate.

## Private vulnerability reports

Use GitHub private vulnerability reporting under the repository Security tab. Never publish credentials or private state.
