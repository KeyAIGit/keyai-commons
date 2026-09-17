# Community phase privacy

The project website is a static page. It does not enroll devices, send hardware inventories, request training permissions or download model/data files. EN/RU preference is stored in browser localStorage. GitHub Pages and GitHub itself may process ordinary hosting/access information under their own policies; zero project analytics is not a claim of anonymous hosting.

Community membership and public discussions use GitHub accounts and GitHub's privacy rules. Do not put personal documents, private keys, medical/immigration information or confidential datasets in public discussions.

The separate Community Preview stores a boolean `interested` locally under the user's configuration directory `KeyAICommons/community`. It does not send that preference to a coordinator, create a remote registration, subscribe the user to notifications, or authorize CPU/GPU training. A random local browser-session credential protects preference changes and changes on application restart. The local web service listens on 127.0.0.1 only. Choosing an external GitHub link opens GitHub under its policies.

Clear preference removes the saved boolean. Exit stops the local service. Closing a browser tab alone does not close the service, but no trainer exists in this build. The browser and local UI use normal resources to display the interface; “no training” does not mean physically zero CPU use.

No automatic update or OS startup is included. This phase has no remote data retention database to delete from. Future telemetry, native notifications, peer storage or training require a separate disclosed policy and consent design. The older v0.2 developer client has different behavior and remains governed by the repository's historical PRIVACY.md.
