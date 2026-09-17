# Research v1: selected technical path

Status: architecture decisions plus an offline reference, not a public training release. Supersedes an unranked list of framework options. Approved direction: community first; Microsoft Store and X publication on hold.

## D1. One falsifiable objective
Show that four independently operated, compatible learners can train the SAME small decoder on the SAME token budget to near-baseline held-out quality while exchanging substantially fewer bytes than synchronous WAN training. Measure time to that quality, failure loss and total resources. Do not use install counts or a toy-loss decrease as the objective.

## D2. Model, not an invented frontier architecture
Choose **Commons-Lab-22M**, a randomly initialized dense causal Transformer with 22,029,696 unique parameters: 12 blocks, width 384, six query heads and two KV heads (dimension 64), SwiGLU width 1024, RMSNorm epsilon 1e-6, RoPE theta 10,000, tied 8,192-token input/output embeddings, context 512, no biases, no dropout. Residual output projections start with standard deviation 0.02/sqrt(2L); other linear/embedding weights use 0.02. The reference follows known Llama-family components and PyTorch SDPA, not a novel network claim. [S1,S2]

Use a dense decoder first because each admitted GPU can attempt a full local replica and the optimization variables stay inspectable. Do NOT initially put MoE token routing, tensor/pipeline parallelism, or KV-cache traffic across home WAN links. SSM/hybrid and MoE alternatives are deferred until the transport/optimizer hypothesis is tested; this is not a statement that they are inferior. Large local clusters may later form one learner island with fast internal parallelism.

Raw weight payload: 44,059,392 bytes in FP16 or 88,118,784 in FP32. Four FP32 tensors for weights, gradients and two Adam moments occupy about 352 MB, excluding activations, attention/workspace, local/global anchors and Nesterov buffers. Full snapshots and retries add traffic. A 6 GB GPU fit is a TARGET to measure, not verified. FP16 + loss scaling is the intended common Turing-compatible GPU precision; BF16 is not the default for an RTX 2060 cohort. The delivered probe is FP32 CPU only.

A Hugging Face shape configuration is provided, but the current reference uses adjacent-pair RoPE. Do not load third-party checkpoints into it or claim binary equivalence without testing weight-layout conversion. No Meta weights are used. The reference code remains MIT; dependency licenses and future model/data rights remain separate.

## D3. Data and tokenizer
Select **TinyStories V2 GPT-4** as a deliberately narrow English-language optimization benchmark, not the eventual worldwide knowledge corpus. Pin repository roneneldan/TinyStories at f54c09fd23315a6f9c86f9dc80f725de7d8f9c64. Its dataset card lists CDLA-Sharing-1.0. Archive provenance and the license before preparing/distributing a derived subset. This selection is not a blanket conclusion about all source rights or an endorsement of its capabilities. [S3]

Raw train: TinyStoriesV2-GPT4-train.txt, 2,227,753,162 bytes, SHA-256 6418d412de72888f52b5142c761ac21a582f7d1166f0bfbdb5f03ccfdec90443. Raw held-out source: TinyStoriesV2-GPT4-valid.txt, 22,502,601 bytes, SHA-256 6874bae9a4c1a4e7edcf0e53b86c17817e9cf881fc75ff2368da457b80c0585d. Metadata was retrieved; corpus bytes and license text were NOT downloaded in this iteration.

Preparation contract: UTF-8; LF newlines; Unicode NFC; split only on the documented end-of-text delimiter; hash normalized story bytes; exact-deduplicate before assigning train/development/final-test. Use the upstream held-out file only for the final test. Within the upstream train file, hashes modulo 1000 in 0..9 form development and 10..999 form training. Exclude every normalized held-out hash from both train and development. Record near-duplicate audit separately; exact hashing does not solve semantic contamination.

Train a byte-level BPE tokenizer with exactly 8,192 entries including fixed special tokens on TRAIN only, on the first 50,000 unique training stories in lexicographic SHA-256 order. Pin the tokenizer implementation/version and output hash before G1. Freeze a deterministic training stream and tokenize into little-endian uint16 chunks of 1,048,576 target tokens (about 2 MiB). Append EOS between stories; use contiguous 513-ID windows at stride 512; score 512 targets. Handle the last window explicitly; do not count padding or the same boundary twice. Publish the list of normalized story hashes, token counts, all chunk hashes and preparation config.

The prepared token corpus and trained BPE are NOT produced yet. This is an explicit G1 prerequisite, not a silently substituted generated dataset. G0 uses content-hash-separated integer sequences to test implementation only; it cannot validate language quality.

## D4. Optimization and the first transport boundary
Implement/reproduce a simple **DiLoCo-style** reference first: AdamW local steps; delta = parent weights minus locally trained weights; token-weighted aggregation; SGD Nesterov outer update. In the homogeneous no-failure run all workers process equal target-token counts, so weighting is equal. Inner moments persist across ordinary synchronization; replacing weights must not recreate optimizer objects. Use FP32 aggregation in the reference. [S4,S5]

Primary hypothesis: H=8 local steps between exchanges; H=32 is the predeclared comparison. Outer learning rate 0.7, momentum 0.9; inner learning rate 4e-4, betas (0.9,0.95), epsilon 1e-8, weight decay 0.1, clip norm 1.0. Warm up over the first 5% of the token budget, then cosine decay to 10% of peak LR. Apply the same global processed-token schedule to compared runs. G0 intentionally uses a different small-fixture LR; it is not the G1 recipe.

First transport: known invited learners, full local model replicas, same parent per round, zero accepted staleness, immutable receipts and explicit deadlines. Do not prematurely implement asynchronous fragment mixing. DHT discovery/averaging via Hivemind is the selected integration candidate after reference parity tests; its Linux-first support does not imply native Windows/macOS readiness. [S6]

Google's **Decoupled DiLoCo** is the next architectural reference: learner islands, fragments, quorum/grace and token-weighted aggregation. It includes a central synchronizer, and some scale/failure evidence is simulation. It is NOT a ready fully decentralized home-PC backend. Pathways is not embedded here. Preserve an adapter boundary so the stable baseline can later be compared with a reviewed asynchronous implementation. [S7]

TensorFlow Federated is an optional algorithm oracle/simulation reference, not a dependency of the community client. A separate parity task will reproduce weighting/selection behavior. OpenDiLoCo is useful historical code but explicitly marked no longer maintained, so it is not selected as our production foundation. [S8,S9]

## D5. Trust, scaling and public access
Keep initial experiment trust explicit: known honest-but-interruptible participants. Weighting claims, signatures and finite-value checks do not solve malicious gradients, Sybil identities or model poisoning. No anonymous training until a separate threat-model and evaluation gate passes.

Decentralize the control plane separately from the optimizer: multiple independent discovery/data providers; cohort metadata replicated across known operators; immutable, quorum-accepted checkpoint records. A three-operator crash-fault consensus implementation is a candidate for metadata, not a home-grown replacement for Byzantine consensus. During loss of a valid metadata quorum do not advance canonical checkpoints; bounded local work may finish but cannot silently create a competing official history. All cryptographic/quorum transport is UNIMPLEMENTED here.

Do not enroll millions of workers into one ever-growing synchronous batch. Bound each cohort and study statistical efficiency as concurrency grows. Surplus devices may support independently planned experiments, evaluation, data integrity and serving only when useful roles are measured. Global aggregation/reconciliation across cohorts is a future research question, not solved by concatenating weights.

A training release, a public inference service and a compact local model are separate deliverables. Free access needs serving capacity and fair-use policy; quantized/distilled models need separate quality tests. Donation does not grant equity or require others to donate to access future public models.

## Sources
S1: https://huggingface.co/docs/transformers/model_doc/llama
S2: https://docs.pytorch.org/docs/2.10/generated/torch.nn.functional.scaled_dot_product_attention.html
S3: https://huggingface.co/datasets/roneneldan/TinyStories
S4: https://arxiv.org/abs/2311.08105
S5: https://docs.pytorch.org/docs/2.10/generated/torch.optim.SGD.html
S6: https://github.com/learning-at-home/hivemind
S7: https://arxiv.org/abs/2604.21428 and https://deepmind.google/blog/decoupled-diloco/
S8: https://www.tensorflow.org/federated/tutorials/building_your_own_federated_learning_algorithm
S9: https://github.com/PrimeIntellect-ai/OpenDiLoCo

Sources inspected 2026-09-17. Selections, dimensions, budgets and thresholds are this project's decisions, not claims certified by those authors.
