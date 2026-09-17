# Offline research reference v1

Start with [the Russian overview](../docs/research-v1/README_RU.md), [decisions](../docs/research-v1/DECISIONS.md) and [the experiment contract](../docs/research-v1/EXPERIMENT.md). This directory does not alter the Community Preview or legacy coordinator. No process starts on import. No networking, remote dispatch, dataset download, telemetry or publisher account access is implemented here.

From the repository root, the lightweight contract tests require only Python:

```sh
PYTHONPATH=research python3 -m unittest discover -s research/tests -p 'test_contracts.py' -v
```

The model and optimizer sanity checks require PyTorch. They were actually run on Python 3.13.5 and PyTorch 2.10.0+cpu with two CPU threads in the assistant's Linux environment, not the owner's GPU. Pin/install dependencies in an isolated environment, not a user's application environment. `requirements.txt` is a direct dependency pin, NOT a fully hashed transitive environment lock.

```sh
PYTHONPATH=research python3 -m unittest discover -s research/tests -v
PYTHONPATH=research python3 -m commons_lab.probe --output /tmp/commons-probe-new.json
PYTHONPATH=research python3 -m commons_lab.sanity --method diloco --local-steps 8 --seed 11 --output /tmp/commons-sanity-new.json
```

On Windows PowerShell, set `$env:PYTHONPATH='research'` first, then run equivalent `python` commands. CUDA is NOT required for these checks. The probe only uses CUDA with an explicit `--device cuda` and a suitable existing PyTorch build; its default CPU result is not a GPU performance claim. The scripts refuse to overwrite a named output, but do not install or enforce an OS security sandbox.

The 22M probe uses three FP32 optimizer steps on one repeated random 128-token batch. The comparative sanity script uses a 102,720-parameter decoder and generated integer sequences with content-hash-separated train/validation partitions. All four logical learners run sequentially in one process. Both small repeated patterns and limited vocabulary make this an implementation fixture, not evidence about human language or generalization broadly.

Compare `single`, `fedavg`, `diloco` with H8 and `diloco` with H32, seeds 11/23/37, 128 local/global steps and 32,768 aggregate target tokens. Source and raw results are archived. Final NLLs must NOT be treated as the G1 held-out-language result; fixtures use different LR/batch/context/data. The displayed byte count is a formula for a hypothetical FP32 star exchange, not network IO. CPU wall times do not represent parallel speedup.

`commons_lab/protocol.py` is an offline crash-fault state-machine sketch. It has no cryptographic signatures, identity service, durable storage, distributed consensus or full training receipt validation. A finite vector from an authorized string ID can still be wrong; do not expose this object as a network service.

Full-corpus preparation, BPE training, G1/G2 training driver, physical-host transport, complete optimizer checkpoint/resume and OS resource/notification controls are not delivered here. Their exact prerequisites and acceptance gates are tracked rather than reported as complete. `results/SUMMARY.json` contains current evidence and negative observations.
