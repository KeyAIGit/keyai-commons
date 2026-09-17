# KeyAI Commons: community-first architecture

**Design proposal, revision 2026-09-17. Not a deployed decentralized training network.**

The purpose is to make useful, inspectable AI research possible with voluntarily contributed computers. Joining the community is not permission to use a device. The public product currently recruits people to discuss, review and build the foundation. The separate Community Preview executable has no training implementation or remote coordinator client. Earlier v0.2 CPU releases remain developer experiments, not the proposed production system.

## 1. A concrete first objective

Do not wait for one million installations before testing the core claim. Demonstrate that a small set of independently operated, intermittently available computers can improve one agreed model to a specified held-out quality target, at a measured total resource cost. Compare with the same model/data on one machine. A successful scheduler, a decreasing toy loss, or a large download count alone is not that result.

The first research workload should be project-generated synthetic data and a small model that fits entirely on the weakest admitted GPU. This avoids downloading a huge corpus before the protocol is understood. A subsequent language experiment should use a reviewed, immutable subset of licensed public text, not personal files. Proposed scale: 20–100 million parameters before any billion-parameter goal. This is an experiment design, not a claim that such a model is generally useful or that the current client supports it.

Separate five roles: community member, data preparation contributor, training worker, independent evaluator, and voluntary storage/relay provider. A person may choose any available role; no role implies legal ownership, payments or guaranteed inference. The code, data and weights each require their own license. MIT on this repository does not license every future dataset or model.

## 2. The right starting technologies

The Google Cloud article describes federated learning: data stays on clients and model updates are combined, often by a central server. Our initial goal is different: volunteers contribute computing power over a shared, licensed dataset. These are related distributed optimization problems, but not the same data/privacy product. We should not call downloaded public text “private data kept on device.” [S1]

**TensorFlow Federated** is a useful research and simulation reference, including federated computation and multi-machine simulation. It is not an installable, ready-made million-home-PC orchestrator. Reproduce aggregation, selection and dropout baselines in a controlled simulator; do not ship a bespoke training algorithm merely because the prototype runs. Google's large-scale federated system paper is a valuable source on selection, availability and operational separation. [S2, S3]

**Hivemind** is the leading candidate to investigate for our peer-to-peer training experiment: its project explicitly supports decentralized PyTorch training, a distributed hash table and decentralized averaging. Its documented OS baseline is Linux; Windows support is experimental through WSL, and macOS has limitations. Native one-click Windows/Apple-Silicon support therefore remains our integration work, not something a dependency magically supplies. Pin and review a specific version before using it. [S4]

**Flower** is a useful comparison for controlled client/server experiments, scheduling and transport. Its SuperLink/SuperNode architecture is not automatically a fully decentralized topology. Review the licenses and distribution conditions of every selected component/version, especially server components; do not assume a project name guarantees that all current offerings are unrestricted. [S5]

**DiLoCo, Streaming DiLoCo and Decoupled DiLoCo** motivate longer local optimization intervals and less frequent inter-worker communication. These papers and Google's 2026 description are evidence about the tested systems, not a demonstration that millions of arbitrary home GPUs can train a frontier model efficiently. The first benchmark must test optimizer drift, stale updates, compression and convergence on our actual workload. [S6, S7, S8]

Decision: keep the current Go code as a small safety/protocol demonstration, build a reproducible Linux research baseline around a reviewed existing training stack, and put the community UI around it only after measurements justify the transition. Do not graft a giant trainer into the current tiny server.

## 3. Separate planes and authority

```text
People propose code and campaigns
          |
          v
Public campaign specification + independent review
          |
          v
Signed campaign manifest, replicated catalog and revocations
          |
          +----> participant's LOCAL permission policy
          |                 |
          |                 v
          |         eligible? notify? resources within budget?
          |                 |
          v                 v
Peer discovery / regional cohorts / time-bounded task leases
          |                 |
          |        local, reviewed trainer and bounded inputs
          |                 |
Data mirrors <----> cache --+--> signed update commitment
                                      |
                         evaluation + aggregation committee
                                      |
                         versioned checkpoint + evidence
                                      |
                         independently replicated storage
```

The **community plane** handles proposals and review. The **control plane** announces campaigns, discoverable peers and leases. The **data plane** distributes immutable chunks and checkpoints. The **compute plane** runs local optimization. The **verification plane** assesses updates and resulting models. These planes must not all share one privileged key, one host, or one failure mode in the decentralized target.

A maintainer merging source code does not authorize a campaign. A campaign committee approving a model does not authorize a user's GPU. The local participant policy always wins. Nobody receives remote shell access merely because a manifest is signed.

## 4. What “decentralized” must mean here

Distribution of work over home computers is not full decentralization. A single founder-controlled scheduler, mandatory website, dataset mirror or signing key is still a central dependency. We propose a progression with explicit exit tests rather than relabeling the current server:

| Layer | First invited experiment | Decentralized target / required evidence |
|---|---|---|
| Discovery | Known invited peers | Multiple independent bootstrap operators; cached peer records; one bootstrap loss does not stop discovery |
| Data | Two mirrors with identical content hashes | Independently operated replicas, repair, optional peer serving; one publisher outage does not make all required chunks unavailable |
| Scheduling | One inspectable scheduler as a baseline | Cohort-level leases and independently operated coordinators; worker failover without accepting a task twice |
| Model acceptance | One trusted verifier, fully disclosed | Per-campaign verification committee and a defined quorum protocol with epoch, parent hash and replay protection |
| Campaign authorization | Founder key for laboratory tests | Distinct accountable approvers and threshold policy, public change history and revocation |
| Client releases | Maintainer-selected version | Reproducible builds, independently checked provenance, protected release authority; participants still choose trust roots |
| Governance | One named maintainer | Public role/succession rules and real independent maintainers, not a fake claim of community control |

A quorum is not, by itself, a complete Byzantine consensus algorithm. We must specify committee membership, equivocation evidence, conflicting epoch resolution, partitions, timeouts and liveness. During a partition, a worker must not accept an unfinalized checkpoint as the canonical successor. It may finish a bounded local lease or pause; reconciliation cannot silently count incompatible updates twice. Initially, test crash fault recovery with known honest operators. Adversarial consensus requires a separate design review before anonymous participation.

No blockchain is required to identify immutable content or to run the first experiments. A token would add accounting, abuse and legal complexity without solving training correctness. Full elimination of every trust assumption is not promised. Each campaign states exactly whom participants are trusting and for what.

## 5. Data: one agreed version, many copies

There should be a single **logical dataset version**, not a single physical database that everybody must stream through. A signed manifest specifies provenance, licenses, preprocessing/tokenizer versions, immutable split definitions, chunk hashes, compressed and uncompressed sizes, records/tokens and mirror locations. A task references a dataset hash and shard/range, never a freely supplied arbitrary download URL.

A proposed initial distribution flow:

1. Curators generate the synthetic baseline or review permitted public sources. Keep source attribution, exclusions, quality criteria and dataset/model licenses explicit. Never scrape participants' documents, browsing history or private chats.
2. Produce deterministic normalized records and tokenized training blocks. Fix the tokenizer and its hash. Remove duplicates across train and evaluation splits; record contamination checks. Lock a held-out evaluation set before experiments.
3. Pack immutable chunks, initially about 16–128 MiB depending on measured bandwidth and storage behavior. Publish size, SHA-256 and a signed manifest; a later Merkle structure can support efficient partial verification. Size is a tunable design choice.
4. Workers first fetch the small catalog, estimate transfer/storage needs and apply their budgets. Download only assigned chunks, resume safely, validate before use, and cache within a local quota. Corrupt or unlicensed entries are rejected, not retried indefinitely.
5. Start with independent HTTPS mirrors, later add opt-in peer distribution. A storage role must disclose upload bandwidth, serving scope, IP exposure and deletion controls. Content addressing detects changed bytes; it does not prove dataset quality, legal permission or permanent availability. IPFS persistence requires actual retaining/pinning nodes. [S9]
6. Replicate complete, versioned checkpoints with recoverable manifests. Training state includes optimizer state, scheduler/random state and accepted-update position, not merely model weights. Never claim recovery from “weights replicated” when optimizer state is lost.

For later text-data review, FineWeb-Edu is a candidate corpus, not an approved automatic download. Its publisher lists Parquet and ODC-By; the project still needs to review attribution, content rights, sensitive records, subset size and evaluation contamination. A dataset-level license does not automatically resolve every right in underlying web content. No such corpus is downloaded by the Community Preview. [S10]

**Example traffic, not a benchmark:** 10 GB sent separately to 10,000 volunteers is 100 TB of distribution. A home server offering 100 Mbit/s upload has an ideal lower bound of about 93 days to send 100 TB, before protocol overhead. Peer caches and mirrors matter. They do not make bytes or electricity disappear. All bandwidth numbers must specify decimal GB/TB or binary GiB/TiB.

## 6. Compute, memory and communication

CPUs can train neural networks; the existing tiny experiment does so. The practical aim of large neural-model training calls for suitable GPUs because throughput and memory become decisive. Do not advertise every CPU as a GPU-equivalent contributor. Useful CPU/storage roles need measured tasks of their own, such as deterministic data checks and evaluation that fits their capabilities.

A simple training-state budget illustrates why adding nominal device memory is misleading. Under one common mixed-precision Adam layout, approximately 16 bytes per parameter are needed for weights, gradients, master weights and moments, before activations, buffers and framework overhead. For 1 billion parameters that is roughly 16 GB before those extras. Different precision, optimizers, sharding and recomputation change the number; measure the selected implementation. Ten million 8 GB GPUs do not become one low-latency 80 PB GPU.

Prefer **local model replicas** on compatible GPU cohorts for the first Internet experiment. Pipeline/tensor parallelism across slow, unreliable WAN links can put sequential communication on the critical path; replicated disk shards do not solve that. Larger multi-GPU “islands” may later use fast local links internally and infrequent inter-island synchronization. Select cohorts using measured VRAM, throughput, upload, latency, availability and supported kernels. A hardware marketing name alone is not admission evidence.

Proposed workflow: download an accepted checkpoint, perform a bounded number of local steps on assigned data, submit an update tied to the base hash and task lease, evaluate and aggregate, then publish a new accepted checkpoint. Tune steps per exchange against model drift. Reject or separately account for updates beyond a documented staleness bound. Do not average weights trained from unrelated checkpoints or data policies blindly.

For intuition, a 100-million-parameter FP16 update is about 200 MB uncompressed. At a 20 Mbit/s upload rate, its ideal one-way transfer takes 80 seconds. If compute takes only seconds, communication dominates. Longer local steps or compression may help but can change convergence. The correct objective is **time and total cost to matched held-out quality**, not the highest accepted-update count.

## 7. Availability and recovery

Workers have expiring leases, heartbeats and unique task/attempt IDs. On voluntary pause or disconnection, the scheduler can reassign uncompleted work after the lease expires. A late result is checked against the accepted ledger so it cannot count twice. In a decentralized target, this deduplication state also needs replication and a conflict protocol.

A completed, accepted contribution persists even when its device leaves. Unfinished local work can be lost; state that honestly. Checkpoint intervals bound the loss. Retain multiple accepted checkpoint generations; verify restorability in a real restart test. Replication must span independent devices/operators and failure domains, not several folders on the same PC. Erasure coding is a possible later optimization, with measured repair and bandwidth costs.

“Any computers that remain online” is too broad. Training can continue only while enough **eligible** workers, required data replicas, verification capacity and consensus quorum remain. If those conditions fail, pause safely and resume from a verified checkpoint. Users must be free to close the app, sleep or shut down. No penalties, scary “do not switch off” warnings or attempts to inhibit shutdown.

## 8. Standing permission and notifications

The future model is not repeated 15/30/60-minute clicks. A participant may authorize recurring participation within a **specific campaign policy**. Store consent locally with the approved workload/build hash, model/dataset manifests, permitted campaign authority, device roles, resource/traffic/disk budgets, time windows and a user-chosen expiry/review rule. A standing opt-in must be revocable and must not mean permission to run unknown future models or arbitrary code.

Changing data, executable capabilities, authority or resource ceilings requires renewed approval. Enrollment, local interest, update installation, campaign approval and execution are separate states. Default all capabilities off. Autostart after login and resume after reboot, if later implemented, need separate explicit opt-ins; the current Community Preview has neither.

Before a task starts, show a native notification and persistent tray/menu-bar status: campaign/model, data to download, devices used, estimated duration, configured budgets, pause/cancel and “do not ask for this campaign again.” Estimates derive from a local benchmark and are ranges, not promises. If the required visible notification channel is unavailable, fail closed unless the user previously chose a clearly explained alternative. Observe platform notification permissions and Do Not Disturb behavior. The website notification is only a visual demo; no native tray or automatic training feature is implemented yet.

A task must respect both a local wall-clock lease and a cooperative cancellation path. For GPU kernels, stopping is not literally instantaneous: define and test a bound, terminate the isolated worker if needed, and never falsely display “stopped” while work is still running. The future agent must prioritize new foreground use, battery transitions, thermal conditions where reliably available and the user's own limits. Pacing is not an enforced hardware power cap.

## 9. Safety and integrity

Three distinct checks are needed: publisher signing identifies a distributed application; signed manifests authenticate campaign authority; content hashes identify bytes. None proves that a computation is safe, useful or correct.

Keep executable tasks allowlisted and versioned, with no remote shell, downloaded scripts, dynamic arbitrary model code or unsafe pickle deserialization. Use bounded tensor/data formats, size/dimension checks, storage quotas and restricted outbound hosts. Run a worker with least privilege and evaluate OS-specific isolation. Containers and GPU drivers do not provide a universal proof of isolation. Independent review and supply-chain provenance remain release gates.

Threats include malicious participants submitting fabricated updates, data poisoning, Sybil identities, checkpoint rollback, compromised mirrors, coordinator takeover, denial of service, malicious contributor PRs and stolen signing keys. Full reference replay catches certain wrong results but doubles work. Sampling, duplicate tasks, held-out validation and robust aggregation have measurable detection limits; they are not a universal cheap proof of training. Set a threat model and measured tolerances before replacing replay. Secure aggregation can conflict with inspecting individual updates. Model updates can leak information; the word “federated” is not a mathematical privacy guarantee.

No claim of ASI safety is made. Even a trustworthy client can train an unsafe or low-quality model. Evaluate model behavior, data memorization and intended uses separately from host security. Document dataset, model and client risks in separate cards.

## 10. Evidence gates, ownership and effort

| Gate | Required acceptance evidence | Suggested scope |
|---|---|---|
| Community readiness | Readable website, public design, clear no-compute state, issue/discussion ownership | Current iteration |
| Algorithm baseline | Reproducible quality/cost baseline with frozen data and optimizer | One GPU and simulated workers |
| Invited network test | Distinct physical hosts and networks, pauses, restart, replay/corruption tests | 3–10 known devices |
| Useful GPU pilot | Matched-quality comparison, energy/traffic/VRAM, convergence under dropout | 10–50 suitable GPUs |
| Federation test | Independent operators, failover, data repair, committee conflict tests | 3 or more operators |
| Public capacity trial | Reviewed packages, rate limits, abuse handling, independent review | 100–1,000 admitted nodes, only after earlier gates |

These are proposed scopes, not verified capacity. Never skip them because community membership is high. Schedule estimate for a small competent team: 1–2 weeks for architecture review and reproducible baseline, 4–8 weeks for an invited useful GPU experiment, several additional months for robust federation and distribution. These are engineering estimates with major algorithm/security uncertainties, not a promise of frontier training or a million-node launch date. The founder plus AI assistance is not an independent security team.

Needed specialties: distributed ML/optimization, systems/network engineering, endpoint security and software signing, data curation/licensing, accessible product design, and an accountable operations maintainer. Public PRs with automated checks and explicit maintainer decisions are the collaboration mechanism. Use GitHub Discussions initially, not several disconnected chat systems. No automatic merge based on popularity and no contributor access to production/signing secrets.

Release decisions and campaign decisions are separate. The founder currently owns the repository; this is not yet decentralized governance. Invite trusted maintainers transparently, record responsibilities, and adopt independent approvals for sensitive code once independent reviewers actually exist. Anyone can fork MIT-licensed source; a fork cannot alter official clients or acquire compute authority.

## Sources checked 2026-09-17

- S1: [Google Cloud: what is federated learning](https://cloud.google.com/discover/what-is-federated-learning)
- S2: [TensorFlow Federated](https://www.tensorflow.org/federated)
- S3: [Bonawitz et al., Towards Federated Learning at Scale](https://arxiv.org/abs/1902.01046)
- S4: [Hivemind project and platform requirements](https://github.com/learning-at-home/hivemind)
- S5: [Flower architecture](https://flower.ai/docs/framework/explanation-flower-architecture.html)
- S6: [DiLoCo](https://arxiv.org/abs/2311.08105)
- S7: [Streaming DiLoCo](https://arxiv.org/abs/2501.18512)
- S8: [Decoupled DiLoCo, 2026](https://deepmind.google/blog/decoupled-diloco/)
- S9: [IPFS persistence](https://docs.ipfs.tech/concepts/persistence/)
- S10: [FineWeb-Edu dataset card](https://huggingface.co/datasets/HuggingFaceFW/fineweb-edu)

Numbers in this document are explicit arithmetic examples or planning targets unless attributed otherwise. Source publication does not certify this project's implementation. No listed training framework was installed or benchmarked by this architecture-writing step.
