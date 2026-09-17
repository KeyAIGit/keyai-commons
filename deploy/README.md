# Hosted preview and durable deployment

The public website is not a coordinator. A coordinator needs HTTPS, private state and an operator key.

## Operator identity

On the organizer's private computer, run `keyai-commons operator init --data PRIVATE_OPERATOR_DIR`.
This prints only the PUBLIC key. The private key remains in `operator-key-private.json` and must never enter Git, release ZIPs or screenshots.
Use the public key for `--operator-key` on the coordinator. Without that flag the remote operator endpoint is disabled.
The local admin dashboard remains loopback-only regardless of this option.

## Durable host

`Dockerfile` and `deploy/compose.yaml` provide a non-root coordinator with a named state volume.
Set `COMMONS_PUBLIC_URL` to your HTTPS origin and `COMMONS_OPERATOR_PUBLIC_KEY` to the public key.
From `deploy`, run `docker compose up -d --build`. Place a TLS reverse proxy in front of loopback port 7860.
The example Caddy configuration is a template, not an already deployed proxy.
The named volume must be backed up privately. Stop the service before a consistent backup.
Restore the entire volume, including identity and state, with original permissions. Restart never resumes a round or publicly opens enrollment.
Do not expose the Docker socket, local dashboard, operator key or volume contents.

## Commands from the organizer's computer

```
keyai-commons operator status --url https://YOUR-HOST
keyai-commons operator open --url https://YOUR-HOST --data PRIVATE_OPERATOR_DIR
keyai-commons operator start --url https://YOUR-HOST --data PRIVATE_OPERATOR_DIR --steps 800 --nodes 3 --seconds 120
keyai-commons operator stop --url https://YOUR-HOST --data PRIVATE_OPERATOR_DIR
keyai-commons operator close --url https://YOUR-HOST --data PRIVATE_OPERATOR_DIR
```

Each control command is signed, expires after 45 seconds, and is bound to the exact origin and current server instance. The server accepts only start, stop, finalize and enrollment open/close. It rejects reused nonces and previous-boot commands. No command contains executable code.
Opening enrollment publishes the participant connection code. Closing it hides that code and rejects new joins, but does not revoke existing participants or stop an active round. Use `stop` separately.

## Ephemeral hosted experiment

For a free test host without durable storage use `--persistence ephemeral` and a writable temporary data directory.
Restart can erase registrations, model checkpoints and the task signing key. The operator public key must remain configured externally; the operator must reopen enrollment. Participants must explicitly reconnect and consent again.
This is suitable for a bounded network test, NOT long-lived contribution accounting, guaranteed availability or mass enrollment. Do not use uptime-pinging tricks to evade the provider's free-tier limits.

## Capacity and security gates

256 registered clients, 32 target participants/round, three assignment attempts per target, 30..240-second rounds, at most 1200 steps/task and a 30-second local task deadline. Dropped clients' empty slots become eligible for reassignment after 12 seconds without heartbeat.
Registration has a per-source-IP limit. Behind a proxy all clients may share that source and hit the limit; do not trust arbitrary X-Forwarded-For. Configure admission at a trusted edge before broad testing.
Full result replay doubles work and is NOT scalable verification. No GPU or LLM workload is included.
Signing certificates, notarization, clean-machine tests and independent security review are still required before broad public distribution.
