First distributable preview of Anna's Archive CLI.

- Search, inspect records, list sources, download files and diagnose mirror access.
- English CLI and documentation, JSON error codes, filtering, Cookies and proxy support.
- Prebuilt wheel and five native standalone archives with SHA-256 checksums and build attestations.
- Each published artifact passes local HTTP fixture smoke tests on its target platform.

**Known limitation:** successful live AA search/detail/download acceptance is still pending.
Tested mirrors required browser verification. This CLI does not execute browser challenges.
The binaries are not OS-signed or notarized. See README for platform baselines and install commands.

Python packages can be run directly from this GitHub release using uvx. PyPI publication
is performed separately after the Trusted Publisher has been configured.
