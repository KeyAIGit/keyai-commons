# Roadmap and evidence gates

The long-term goal is useful, community-operated AI compute. Node counts are not proof of training efficiency or model quality. This is a research roadmap, not a promise of ASI, ownership or financial returns.

## Stage 0: inspectable local pilot

Available: fixed 65-parameter CPU training, explicit consent, signed tasks, operator commands, reference replay, checkpoints and dropout deadlines. Current hard limits are 32 nodes per round and 256 registrations. Initial tests used multiple processes on one host.

## Stage 1: invited cross-network pilot

- Verify installation, consent, pause and exit on clean Windows/macOS/Linux machines.
- Produce reviewed, reproducible, signed/notarized packages and publish checksums.
- Deploy a stable HTTPS coordinator with private administration, restricted enrollment, backups and monitoring.
- Test at least three physical machines on different networks, including dropout, network failure, restart and consent expiry. Publish a redacted report with exact versions and failures.

Do not announce a generally available network before these gates pass. Hosting a GitHub repository or a static website is not deploying a training coordinator.

## Stage 2: useful measured GPU work

Introduce one reviewed, fixed, allowlisted GPU workload. Document dataset rights, hardware compatibility, VRAM needs, electricity and bandwidth costs. Compare model quality, accepted throughput, wall time and total costs against a single-machine baseline. CPU-only participants need separate useful roles, not fake GPU-equivalent credits.

## Stage 3: scalable validation and storage

Replace full reference replay only after a threat model and measured fraud-detection tradeoffs. Evaluate Sybil-resistant admission, rate limits, checkpoint distribution, shard replication and recovery. Do not imply that signatures alone prove correct computations or that storing a shard grants legal ownership.

## Stage 4: scaling experiments

Increase admitted nodes only when earlier measurements support it. Publish availability, failed work, communication overhead, recovery times and learning curves. Million-device or frontier-model claims require evidence not yet present in this repository.
