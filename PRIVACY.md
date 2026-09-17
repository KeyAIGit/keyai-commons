# Pilot privacy boundaries

The client uses synthetic data, not documents, browser history, private chats or personal training datasets. It sends a pseudonymous node ID, OS/architecture, readiness, protocol messages and computed model updates. The coordinator and any hosting proxy can observe connection IP addresses. Pseudonymous does not mean anonymous.

Local configuration stores connection credentials and state under the operating system user configuration directory in `KeyAICommons`. Never publish those files or operator URLs. Consent does not persist across process restarts. Pause stops participation but does not delete coordinator records.

This repository does not operate a public coordinator or set a production retention policy. Each future operator must disclose hosting, logs, retention, deletion procedures and contact details before accepting participants. Do not send private prompts or datasets to this pilot. No confidentiality, legal ownership or future inference entitlement is implied.
