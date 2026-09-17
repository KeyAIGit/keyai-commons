# Distribution and Microsoft Store preparation

Status: preparation only. No Store account, verified publisher identity, reserved app identity, certificate, certification approval or Store listing is claimed by this repository.

## Microsoft Store without the Azure signing subscription

The current official onboarding route is https://storedeveloper.microsoft.com/ . Microsoft's May 2026 documentation describes free registration for both individuals and companies through the new flow. Other legacy entry paths can differ. Use the official new route; do not purchase Artifact Signing merely to register for the Store.

Store-distributed packaged applications use Microsoft's distribution signing. This is different from putting an unsigned EXE or a locally self-signed MSIX on GitHub. A Store listing that links an external EXE/MSI is also not the same delivery/signing path. Outside the Store, publisher trust and reputation still need to be addressed. Keeping an ordinary home computer online does not make it a publicly trusted signing authority.

The user's participation is required for Microsoft sign-in/MFA, individual identity verification or company records, legal account ownership, and any contractual confirmation. Never invent a Publisher value, identity document, reserved application name or authorization. Artifact Signing's paid service is optional, not a necessary recurring charge for the selected Store-hosted MSIX route.

## A genuine closed preview

Choose **Private audience on the first submission**, using an actual private group of consenting testers' personal Microsoft account emails. Do not publish public/unlisted and then claim it is private. Microsoft's visibility documentation says private-audience reviews are visible to the developer in Partner Center, not published in the Store, even after a later change to Public. Public-to-private conversion is not available after a public submission. Unlisted links alone do not provide a closed audience.

This is beta testing, not suppression of feedback from public customers. State the exact limitations clearly, request feedback, and provide functional behavior. Preview wording does not waive certification, privacy or minimum-functionality requirements. A minimal local interest checkbox alone may not be enough for Store acceptance. Do not submit a placeholder just to acquire trust or reserve future compute access.

## Submission checklist

1. The owner signs in through the new onboarding flow, chooses the correct individual/company status, and completes verification. No Azure subscription is provisioned by these scripts.
2. Reserve an app name and copy the assigned Package/Identity/Name, Publisher and publisher display name from Partner Center. Keep account/session credentials private.
3. Select a reviewed commit and build the **separate Community Preview** target, not the old trainer. Run native tests. The preview must not later gain background training through an undisclosed update.
4. Run `packaging/windows/build_msix.py` with the real assigned identity fields. The output is an unsigned submission package; Microsoft signs through the selected Store distribution process. A local validation package is not installable proof of trust and must never be uploaded as a reserved identity.
5. Test packaging and Windows App Certification Kit on a suitable test machine. The desktop app requests `runFullTrust`; explain why a Go desktop process and local browser listener are needed. This is not a sandbox certification.
6. Fill privacy URL, listing, accurate screenshots, category, IARC ratings, supported architectures, free price, Private audience and tester list. Avoid fabricated age-rating answers. Leave publication manual pending acceptance.
7. Upload through the authenticated owner account and submit for Microsoft certification. Record the submission ID and actual result. Do not announce a Store download before it exists.

## macOS from Windows

The account can be enrolled through Apple's website, but trusted Mac distribution requires Developer ID/signing/notarization with Apple's tooling. Build and test Mac artifacts on a real Mac or a macOS CI runner; Windows-side Go cross-compilation alone is not notarization or a native UI test. Apple Developer Program has a membership fee. Do not spend or enroll on the owner's behalf without their completion/approval. Keep signing secrets away from untrusted PR workflows. Standard GitHub-hosted runners are available for public repositories under GitHub's terms; they do not supply an Apple certificate for free.

## Linux and other platforms

Start with reviewed portable builds and later .deb/.rpm or Flatpak as appropriate, with desktop launchers, clean removal and authenticated updates. Repositories and Store listings require their own trust/acceptance work. Mobile platforms are separate products because lifecycle, background execution and supported ML runtimes differ; they are not “one more binary.” The browser community page works now without installing a computing agent.

## Official references checked 2026-09-17

- https://learn.microsoft.com/en-us/windows/apps/publish/partner-center/open-a-developer-account
- https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/visibility-options
- https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/create-app-submission
- https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation
- https://developer.apple.com/help/account/membership/program-enrollment/
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
