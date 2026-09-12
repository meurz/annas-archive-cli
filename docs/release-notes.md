Browserless live downloads in Anna's Archive CLI 0.2.0rc2.

- Real public-domain search → details → free-source download → MD5 and EPUB checks.
- Fix empty search titles and missing details caused by the current website layout.
- Retry recognized challenge pages with equivalent percent-encoded requests, using
  ordinary HTTP and the same Cookie jar. No browser or new runtime dependencies.
- Wait for the free-source countdown within `--max-wait` (300 seconds by default).
- Wheel and five native standalone archives, checksums and build attestations;
  each artifact passes local HTTP fixture tests on its target platform.

Run immediately:

```sh
uvx --from annas-archive-cli==0.2.0rc2 anna download 51d2b22ca12a8b470b51f543298b34c9 -o pride-and-prejudice.epub
```

**Limits:** the request fallback relies on current upstream protection behavior;
it is not a universal CAPTCHA solver. Mirrors, source availability and countdowns
can change. See `docs/live-verification.md` for the tested records and hashes.
The binaries are not OS-signed or notarized.

The successful tagged release automatically triggers publication of the same
verified Python distributions to PyPI.
