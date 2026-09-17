# Architecture and exact scope

```
Participant approves a session       Operator starts an explicit round
             |                                      |
             v                                      v
local client UI (loopback+token)       private operator UI (loopback+token)
             |                                      |
             v                                      v
fixed CPU trainer <-- signed job -- coordinator public HTTPS API
             |                         |       |
             +---- local update ------>+       +-- model checkpoint
                                       |
                              reference replay verification
                                       |
                          average accepted local model weights
                                       |
                              next global model version
```

One compiled Go program, three entry modes: `client`, `coordinator`, `demo`.
No third-party Go dependencies. UI assets are embedded. `demo` runs one coordinator
and one participant locally but does not grant consent or start a campaign.

Each round has a single immutable base model/version/hash and independent seeded
synthetic sample streams for each participant. All jobs have the same local batch
count and learning rate, so accepted weights are averaged equally. Every update
is checked against a full coordinator replay with a floating-point tolerance.
Canonical reference results are averaged in sorted node-ID order. This is a tiny
FedAvg-style engineering example, not a benchmark of general federated learning.

No node receives another node's identity, token or update. Public APIs return only
aggregate status and the public synthetic model. Admin endpoints are on a separate
listener. The network address and task-signing public key are pinned in the invitation.
Task envelopes use Ed25519 with node ID, round, base hash, version, model allowlist,
step bounds and a validity interval. Clients never execute downloaded code.

Each participant polls every two seconds using an outbound connection. HTTP redirects
are refused. Request/response body sizes and HTTP timeouts are bounded. Plain HTTP
is accepted only on loopback for development. HTTPS termination is provided by the
operator's reverse proxy in a future external deployment, not by this archive.

A client stops a running task at the next poll if the round disappeared, or if the
coordinator request fails. Worst-case connection timeout adds approximately five
seconds to the two-second polling interval; every task also has a 30-second local
deadline. The pause button cancels locally without waiting for the server. Consent
expires after the selected session length and never survives process restart.
Cancelled tasks are not resumed in the same round. Lost nodes are omitted when the
round deadline expires; this release does not migrate partial optimizer state.

Only accepted contributions are included in checkpoints. Server restart aborts any
in-flight round, preserves the committed model, and requires a fresh operator command.
Atomic JSON replaces state files. A single coordinator process per data directory is
required; this pilot has no multi-writer locking or distributed consensus.

Reference algorithm: H. Brendan McMahan et al., AISTATS 2017,
Communication-Efficient Learning of Deep Networks from Decentralized Data.
https://proceedings.mlr.press/v54/mcmahan17a.html
