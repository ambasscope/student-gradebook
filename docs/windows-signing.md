# Verified Windows publisher signing

Status: the application and current Windows distribution are **unsigned**.
The scripts here prepare release verification and packaging. They do not issue a
certificate, validate the developer's legal identity, subscribe to a signing
service, or change an existing executable into a trusted signed application.

## Prerequisite

Choose a signing provider that supports the publisher's country and whether the
publisher is an individual or organization. Complete its identity validation.
Use an HSM or the provider's cloud signing service as required by that provider;
a USB token on a developer's computer is not directly available to a hosted
GitHub Actions runner. Do not put private keys, certificate passwords or signing
credentials into source control or a chat message.

Microsoft currently limits Azure Artifact Signing public-trust onboarding to
organizations in the US, Canada, EU and UK and individuals in the US and Canada.
Do not assume Thai publishers qualify. Other certificate authorities or managed
signing providers have their own eligibility and prices. SignPath Foundation
has eligibility requirements for open-source projects; this project has
not been accepted into that program. The public-source release is being prepared. No account or
subscription has been created by this implementation.

## Release order

1. Build with `python tools/build_windows.py` as before. This creates an unsigned
   staging folder and ZIP. Do not upload that ZIP as a signed release.
2. The chosen provider signs and timestamps
   `dist/StudentGradebook/StudentGradebook.exe` on the Windows runner. Use SHA-256
   and a supported RFC 3161 timestamp authority. Preserve vendor signatures on
   bundled third-party libraries. Provider integration and credentials remain to
   be configured after a provider and validated publisher are selected.
3. Finalize on Windows:

   ```powershell
   python tools/package_signed_windows.py --expected-publisher $env:WINDOWS_SIGNING_PUBLISHER
   ```

   `WINDOWS_SIGNING_PUBLISHER` is the **exact Subject from the validated
   certificate**, not a name invented for the application. Verification requires
   a trusted embedded Authenticode signature, that exact publisher, a timestamp,
   Windows SDK SignTool success (`verify /pa /all /tw /v`) and a successful
   packaged startup check. Missing tooling, warnings and failures stop packaging.
4. Upload the distribution only if both signing and finalization succeeded.
   Do not use `continue-on-error`, unsigned fallback, or `if: always()` on the
   signed release upload. The existing workflow remains unsigned until the
   provider step and finalizer are connected.
5. Deliver the regenerated ZIP **and** its regenerated checksum manifest. The
   manifest records publisher, certificate thumbprint, timestamp authority and
   the executable hash. Finalization never modifies a signature after validation.

Self-signed certificates are not a public-trust substitute. Tests mock signature
verification to exercise failure handling; they do not create or install a
trusted certificate. Public signing still needs provider identity approval and
credentials. No personal database is involved in signing or packaging.

A verified publisher signature identifies the publisher; it does not certify
that Defender will accept the application. Actual malware false positives can
be submitted separately to Microsoft for review.

## References

- [Microsoft signing options and eligibility](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [SignTool verification](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool)
- [PowerShell Authenticode verification](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/get-authenticodesignature)

## Checks

```sh
python -m unittest tools.tests.test_windows_signing config.test_windows_build
```

Unit tests verify orchestration with mocked signature results; one additional
Windows test executes PowerShell and checks that unsigned input is rejected. A real signed
release must pass the Windows verification above; no signed-release validation
has yet been run with a publicly trusted publisher certificate.

## Planned SignPath Foundation route

The maintainer is an individual in Thailand. Azure Artifact Signing is therefore
ineligible under the cited rules. The intended free route is a SignPath
Foundation application after the public project and first release are available.
Acceptance is not guaranteed.

See [Code signing policy](code-signing-policy.md). The SignPath organization ID,
project slug, artifact configuration, release policy and API credentials are not
yet configured. Maintainer MFA and manual release approval must be set up during
onboarding. Signed files must come from a verified GitHub-hosted build artifact.
The ordinary build workflow remains unsigned until this integration is enabled.

The separate Check Windows signature verification workflow uses no signing
credentials and publishes no application. It has passed the real Windows check
that rejects unsigned input; no publicly trusted signature has been validated.
