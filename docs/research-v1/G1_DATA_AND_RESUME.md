# G1 preparation: language data, complete state and GPU calibration

This is local research, not a public training release, useful assistant or WAN system. The Community Preview, participant permissions, Store and X remain unchanged. Read `research/results/g1-v1/SUMMARY.json` for actual evidence.

## Experiment and data
The exact 22,029,696-parameter decoder, context 512, AdamW, H8/H32 and preregistered token budgets/margins are unchanged. `study.json` remains the historical preregistration; its null hashes and original metadata-only source scope are not a current run log. Prepared identities and remaining gates are recorded separately.

Both immutable TinyStories V2 GPT-4 files were downloaded and checked against the previously selected byte lengths and SHA-256 values. The dataset card and CDLA-Sharing-1.0 text were archived privately. Data, tokenizer vocabulary and checkpoints stay outside Git. MIT on this source code does not change the dataset terms.

Normalization is strict UTF-8, LF, Unicode NFC and stripped outer whitespace. The final-test source takes priority. Normalized content hashes remove exact duplicates and prevent exact train/dev/final-test overlap. Hash modulo 1000 below 10 assigns development within upstream train; the remainder is training. Records are ordered lexicographically by hash within each split.

**Observed source exception:** both hash-verified files end without a delimiter; the training tail is visibly cut off. Both final fragments are omitted under one deterministic rule, with their normalized lengths and hashes recorded. Generic parsing still rejects unterminated input without an explicit omission audit. This adds a conservative EOF rule to D3 before any text training. The failed first index was retained privately rather than accepted or silently repaired.

Byte-level BPE uses tokenizers 0.22.1 and exactly the first 50,000 unique training stories by hash. Vocabulary: 8192 entries; IDs 0/1/2/3: `<unk>`, `<bos>`, `<eos>`, `<pad>`. The actual tokenizer was built twice and compared byte for byte. Training excludes development/final-test text. Unicode and implementation versions and training-identity hashes are recorded.

EOS follows every story. A chunk holds at most 1,048,576 **token IDs** in little-endian uint16, not an independent padded training example. A 513-ID window at stride 512 scores 512 targets and can cross chunks. First ID and incomplete tail accounting are explicit. All chunk and story-ledger hashes are checked; the manifest is committed only when every split is complete. The full miniature pipeline is repeated in tests; the real tokenizer is repeated, but full real-corpus encoding is performed once.

The engine rejects training on held-out splits and permits evaluation only on development from the same manifest. Final test is prepared but not evaluated. Exact disjointness is not semantic or near-duplicate detection: that audit and broader quality review remain pending.

## Complete local recovery
The reference engine has full local replicas. Multiple logical learners execute sequentially on one device; this is not network transport or a speedup result. Checkpoints preserve all server/learner parameters, inner Adam states, outer anchor/momentum, AMP scalers, data cursor and ledger, counted tokens, global/outer positions, and Python/CPU/CUDA RNG. NumPy randomness is not used. Synchronizing parameters does not recreate optimizers.

Snapshots occur at completed global optimizer-step boundaries, preserving different learner states inside an H8 round. Unfinished gradients are discarded on interruption and recomputed from the last committed state. This is bounded loss, not zero lost work under power failure.

Serialization uses dense safetensors plus a bounded JSON tree, not pickle or torch.load. Checks include file/tensor size, depth, finite values, expected hash and immutable names. Writes use flush/fsync and atomic rename in a private single-writer directory. Hashes are not signatures, proof of computation or Byzantine consensus. This is not an independently audited Internet checkpoint format.

CPU tests compare uninterrupted execution with fresh-process resume and inject a write failure. The GPU probe uses the exact 22M model, FP16/GradScaler and four sequential learners: save at global step 7, cross the H8 update through steps 8 and 9, then continue from the same snapshot in a fresh process and compare complete state and losses bitwise. Scope is the recorded environment, not equivalence across versions/platforms or an actual power-cut test.

## Calibration and limits
Calibration uses one local replica, context 512, microbatch 2, accumulation 4, FP16 autocast with FP32 parameters, AdamW and MATH SDPA. Measure 100 optimizer steps after 20 warmup steps. CUDA timing is synchronized; allocated/reserved memory and periodic temperature/power are recorded. Sparse power samples do not measure total energy. Math attention is a deterministic control, not the fastest kernel.

This is not the four-worker G1 global batch or the 16,777,216-token quality screen. Development is sampled at 16 windows for a sanity check, not final acceptance. RTX 5070 measurements are not RTX 2060 compatibility or million-device capacity. The CUDA runs use PyTorch 2.13.0+cu130/Python 3.12.14; CPU reference CI remains PyTorch 2.10.0. Exact resume is scoped within the tested environment. A new Commons venv referenced an existing torch installation read-only; no other project environment was modified.

GPU checks require an explicit corpus/hash, a new output directory and a stop-file path. Internal wall cap: 14 minutes per check. Temperature at 82 C or the owner stop file aborts at the next check. An allocator fraction is not a physical power cap or instantaneous cancellation guarantee. No participant device is enrolled or activated.

## Reproduction
Use a separate environment and install the CPU or hardware-appropriate CUDA PyTorch plus `research/requirements-data.txt`. Run from the repository root with `PYTHONPATH=research`.

```sh
python -m unittest discover -s research/tests -v
python -m commons_lab.fetch_data --raw /private/raw --download-reviewed-corpus
python -m commons_lab.data --raw /private/raw --selection research/configs/dataset-selection.json --work /private/prepared --stage index
python -m commons_lab.data --raw /private/raw --selection research/configs/dataset-selection.json --work /private/prepared --stage tokenizer
python -m commons_lab.data --raw /private/raw --selection research/configs/dataset-selection.json --work /private/prepared --stage encode
python -m commons_lab.gpu_calibration --mode calibration --data /private/prepared/tokens --manifest VERIFIED_SHA256 --output /private/new-calibration --stop-file /private/STOP_REQUESTED
python -m commons_lab.gpu_calibration --mode resume --data /private/prepared/tokens --manifest VERIFIED_SHA256 --output /private/new-resume --stop-file /private/STOP_REQUESTED
```

Use fresh outputs after failed preparation. Do not overwrite an accepted snapshot or treat an incomplete manifest as ready. The historical study gate remains closed; completing these probes does not automatically launch the full screen. Next: review data leakage and the controller, then compare single global-batch AdamW, FedAvg H8, DiLoCo H8/H32 at matched token budgets. Keep three-seed confirmation and margins unchanged. Separate physical hosts, malicious-update defenses and consensus remain future gates.

References: [dataset](https://huggingface.co/datasets/roneneldan/TinyStories), [data terms](https://cdla.dev/sharing-1-0/), [tokenizers](https://huggingface.co/docs/tokenizers/quicktour), [safetensors](https://huggingface.co/docs/safetensors/index), [reproducibility](https://docs.pytorch.org/docs/2.10/notes/randomness.html), [serialization notes](https://docs.pytorch.org/docs/2.10/notes/serialization.html).
