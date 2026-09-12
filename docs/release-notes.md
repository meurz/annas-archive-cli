Clearer CLI next steps in Anna's Archive CLI 0.2.0rc3.

Search results now show copyable download, details and source commands using a real
record MD5. The hints explain how to select another result and choose a download
folder. Record details and source listings also show the next command, including
the correct `--source` index. Explicit mirror, Cookie file, User-Agent and timeout
options carry over into the examples. JSON output stays unchanged.

```sh
uvx --from annas-archive-cli==0.2.0rc3 anna search '"Pride and Prejudice" "Gutenberg"' --lang en --ext epub --sort smallest --limit 3
```

No additional dependencies or browser runtime. Includes the browserless download
and bounded countdown support from rc2. Upstream protection and source availability
can still change; see `docs/live-verification.md` for the tested routes and limits.

Wheel, source distribution and five native standalone archives are available with
SHA-256 checksums and GitHub build attestations. Each artifact passes its platform's
packaging checks. The binaries are not OS-signed or notarized.
