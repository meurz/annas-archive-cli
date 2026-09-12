# Release operations

GitHub is the canonical host for this project. The release branch is `main`.

## Prepare a release

1. Update `src/anna/__init__.py`, CHANGELOG, release notes and pinned README examples.
2. Run `uv lock`, local gates and native packaging checks for available hosts.
3. Merge the reviewed change after required CI checks pass.
4. Tag the corresponding main commit, e.g. `git tag v0.2.0rc1`, and push that tag.

The Release workflow verifies that the tag matches the package version and belongs to
main history. It reruns CI, builds five native targets and runs the installed CLI against
a local fixture server before publishing any artifact. Fork PRs have no publish credentials.
The `github-release` environment and tag permissions restrict publishing. Prerelease tags
stay prereleases; never claim live AA support without a successful acceptance record.

Artifacts include standalone archives, wheel, sdist, installers, SHA256SUMS and GitHub
build attestations. macOS and Windows OS signing is not configured. Linux archives carry
the minimum glibc baseline of their build host, not universal Linux compatibility.

## PyPI Trusted Publishing

The `Publish to PyPI` workflow is manually dispatched with an existing release tag.
It downloads and verifies the provenance of the tested wheel/sdist, then publishes the
same files through OIDC. No long-lived PyPI token is stored in GitHub.

On PyPI, configure a pending publisher for a new project, or a trusted publisher for
an existing project, with these exact values:

| Field | Value |
| --- | --- |
| PyPI project | `annas-archive-cli` |
| GitHub owner | `meurz` |
| GitHub repository | `annas-archive-cli` |
| Workflow filename | `pypi.yml` |
| Environment | `pypi` |

This requires an authorized PyPI account with publishing rights. A GitHub login does
not create a PyPI account or reserve the package name. Until this setup is complete,
use the release wheel URL from README. Once configured, dispatch `pypi.yml` with the
release tag and verify `uvx --from annas-archive-cli==<version> anna --version` in a clean
cache after publication. Do not claim PyPI availability before this check passes.

## Failures and retries

A failed build must not produce a published release. Fix code with a new version/tag.
If publication alone fails, keep the draft and tested workflow artifacts. Verify which
assets exist, compare their checksums, then upload only missing assets and finish the
draft. Do not overwrite a published file or recreate a released tag. PyPI versions are
immutable; do not rebuild an existing version and upload different bytes.

If PyPI partially accepted a release, compare the accepted file digests with the tested
artifacts and publish only the missing original file. Use a new version if content changed.

## Live acceptance

Use the manually triggered Live diagnostics workflow for mirror status without account
Cookies. Keep it separate from required CI. A stable release claiming working AA access
requires a verified mirror, a successful search and record fetch, and an appropriate
file download with integrity verification. Redact and minimize any captured fixtures.
