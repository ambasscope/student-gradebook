# Code signing policy

Status: the app is currently unsigned. SignPath Foundation sponsorship is planned
and has not been approved. The current ZIP must not be described as signed.

Proposed roles (GitHub account):

- Author/committer and reviewer: [ambasscope](https://github.com/ambasscope).
- Signing approver: ambasscope; each release requires manual approval.

Maintainers must use MFA on GitHub and on the signing service. Sign only the
project executable built from the reviewed source commit on GitHub-hosted
runners. Do not sign third-party DLLs under this project's certificate.

After approval, the sponsorship acknowledgment will be:

> Free code signing provided by SignPath.io, certificate by SignPath Foundation.

The verified publisher under this program is SignPath Foundation. The build's
project/product identity remains Student Gradebook. Public releases will link
the matching source commit and [privacy information](PRIVACY.md).

See [SignPath Foundation terms](https://signpath.org/terms) and
[GitHub Actions integration](https://docs.signpath.io/trusted-build-systems/github).
