# Security policy

The latest preview receives fixes; older previews have no maintenance guarantee.

Report vulnerabilities privately using GitHub's **Report a vulnerability** entry under
this repository's Security tab. Do not put credentials, Cookie values or private URLs
in public issues. If private reporting is unavailable, open an issue requesting a private
contact without describing the exploit or disclosing sensitive data.

This CLI makes network requests and writes downloaded files. It validates TLS,
respects Cookie domain/path/expiry constraints, does not execute challenge scripts,
and avoids overwriting existing downloads. It does not establish whether an arbitrary
third-party file is safe to open.

Releases include SHA-256 checksums and GitHub build attestations. Checksums detect
corruption; verify attestations when you need to establish build provenance. Current
standalone executables are not OS-signed or notarized.

Dependency audits run in CI, and Dependabot submits grouped weekly updates. Do not use
untrusted pull-request code in workflows with publishing permissions or account secrets.
