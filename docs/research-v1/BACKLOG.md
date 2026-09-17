# Work packages in dependency order

R0 DONE, implementation sanity only: model dimensions/causality; exact parameter count; outer-update sign; weighted receipts; duplicate/stale/finite-value checks; comparative fixture runs. Evidence lives in research/results. Negative comparisons must remain visible.

R1 NEXT, data owner/reviewer: archive and review TinyStories rights/provenance; verify raw hashes; exact/near dedup audit; content-separated splits; train BPE on train only; publish tokenizer/subset/chunk hashes and data card. Exit evidence: a clean machine produces identical token bytes and no exact split overlap. No personal files. Do not download 2.2 GB before a bounded preparation command and disk/traffic budget are recorded.

R2 NEXT AFTER R1, ML engineer: compare reference components to a pinned upstream implementation; implement AMP/gradient-accumulation parity and complete snapshot/resume (weights, Adam moments, Nesterov state, RNG, LR counters and data cursor); calibration on one GPU. Exit evidence: resumed vs uninterrupted trajectories within a declared numeric tolerance, meaningful sequence-512 throughput and VRAM, finite outputs. No claiming the CPU short-input probe proves GPU admission.

R3 AFTER R2, ML researcher: execute the G1 screen and commit a selected candidate before final-test evaluation; at most the declared runs/resource budget. Record failure and propose a new version if no candidate passes. Exit evidence: seed-level matched-token quality report and budget compliance.

R4 AFTER R3, distributed-systems engineer: integrate a reviewed Hivemind transport adapter on known local peers, then physical hosts and networks. No user-facing auto-download or arbitrary code execution. Exit evidence: measured traffic, dropout and lineage/cancellation tests; traceable versioned job state. Parent/hash checks are not authentication or Byzantine consensus.

R5 AFTER R4, independent operators/security reviewers: select a maintained metadata-consensus implementation and define its crash/adversarial fault boundary; build mirror/checkpoint repair and authority revocation; repeat G3 failures. Anonymous admission requires a separate defense/cost analysis; full replay, sampling and robust aggregation are not interchangeable guarantees.

R6 ONLY AFTER PRODUCT VALUE, desktop packager/accessibility reviewer: genuine offline campaign inspector/capacity planner, useful participant controls, clean install/uninstall and independent signing review. Microsoft Store ON HOLD; no placeholder submission, certificate purchase or registration continuation now.

R7 AFTER RESEARCH REVIEW, public communication: revise X invitation around a defined experiment, independent reviewers and first reproducible results. Do not announce a superintelligence, useful trained model, production backend or GPU fleet on the strength of this repository. No social post is published by this iteration.

Every work package has an owner when a real person accepts it. These role labels do not invent a team. The founding maintainer remains @KeyAIGit. Code acceptance, experiment authorization and device permission are independent.
