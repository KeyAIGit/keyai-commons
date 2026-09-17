# Operator deployment checklist (not performed automatically)

1. Rebuild with a reviewed supported Go compiler. Review code and test the binary.
2. Choose a host you control and a stable HTTPS origin; install a TLS reverse proxy.
3. Launch one coordinator bound to loopback on that host:

```
keyai-commons coordinator --listen 127.0.0.1:18741 \
  --public-url https://YOUR-COORDINATOR-HOST \
  --data /path/to/private-coordinator-state --no-browser
```

Replace the uppercase hostname. Do not publish the state directory or the operator
URL. Proxy only port 18741. The operator listener is a separate random loopback port;
access it via a trusted local browser or authenticated administrative tunnel.
The app deliberately does not open firewall ports, create tunnels, register services
or provision a cloud account.

4. Put the static site and client downloads on your public web host. The coordinator
API does not serve executable downloads; do not point people to dead download links.
5. Open the private operator dashboard, copy the participant connection code, and
provide it to the initial invited testers. This code contains no operator secret.
6. Test Windows/macOS/Linux where claimed; sign Windows releases and notarize macOS.
7. Verify real cross-network dropout, consent expiry, disconnection, retry, restart,
TLS/key pinning, load and authentication failures. Publish honest test evidence.
8. Only then invite more users. The current pilot caps 32 nodes/round and 256 enrollments.

No permanent coordinator has been deployed by this archive. No public URL is supplied
or invented. No money is charged, no hosting subscription is purchased, and no X post
is sent by running any build or demo command.
