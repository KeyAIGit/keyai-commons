# Pilot privacy boundaries

The client uses synthetic data, not documents, browser history, private chats or personal training datasets. It sends a pseudonymous node ID, OS/architecture, readiness, protocol messages and computed model updates. The coordinator and any hosting proxy can observe connection IP addresses. Pseudonymous does not mean anonymous.

Local configuration stores connection credentials and state under the operating system user configuration directory in `KeyAICommons`. Never publish those files or operator URLs. Consent does not persist across process restarts. Pause stops participation but does not delete coordinator records.

This repository does not operate a public coordinator or set a production retention policy. Each future operator must disclose hosting, logs, retention, deletion procedures and contact details before accepting participants. Do not send private prompts or datasets to this pilot. No confidentiality, legal ownership or future inference entitlement is implied.


## 0.2.0 revocation and hosting

The participant can request server-side registration deletion using Leave network and delete my registration. Local enrollment credentials and the last local model are then removed. The request requires a reachable coordinator; failed revocation leaves the client paused with credentials retained for retry. Aggregate model versions/history are not retroactively erased. Infrastructure access logs may retain IP addresses under the host provider's policies.

Discovery explicitly contacts the HTTPS origin typed into the client and pins its returned task key. CPU pacing is local and session-configurable. No GPU model, hostname, documents, browser data or chats are collected by this release. A hosting provider may process requests outside the user's country. Free ephemeral hosts may lose registration/model state when restarted.
