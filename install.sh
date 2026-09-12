#!/bin/sh
# Install a verified standalone release without requiring Python or root.
set -eu

repo=meurz/annas-archive-cli
version=${ANNA_VERSION:-latest}
install_dir=${ANNA_INSTALL_DIR:-"$HOME/.local/bin"}
release_base=${ANNA_RELEASE_BASE:-"https://github.com/$repo/releases/download"}

fail() { printf '%s\n' "Error: $*" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || fail 'curl is required.'
command -v tar >/dev/null 2>&1 || fail 'tar is required.'
if [ "$version" = latest ]; then
    version=$(curl -fsSL --retry 2 "https://api.github.com/repos/$repo/releases/latest" |
        sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
fi
printf '%s' "$version" | LC_ALL=C grep -Eq '^v[0-9][0-9A-Za-z.-]*$' ||
    fail 'Set ANNA_VERSION to a release tag, for example v0.2.0rc1.'
case $(uname -s) in
    Linux) os=linux ;;
    Darwin) os=macos ;;
    *) fail 'This installer supports Linux and macOS; use install.ps1 on Windows.' ;;
esac
case $(uname -m) in
    x86_64|amd64) arch=x86_64 ;;
    arm64|aarch64) arch=arm64 ;;
    *) fail 'Unsupported CPU architecture.' ;;
esac
asset="anna-$version-$os-$arch.tar.gz"
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
printf '%s\n' "Downloading $asset" >&2
curl -fsSL --retry 2 "$release_base/$version/$asset" -o "$temporary/$asset"
curl -fsSL --retry 2 "$release_base/$version/SHA256SUMS" -o "$temporary/SHA256SUMS"
expected=$(awk -v name="$asset" '$2 == name { print $1 }' "$temporary/SHA256SUMS")
printf '%s' "$expected" | LC_ALL=C grep -Eq '^[0-9a-f]{64}$' || fail 'Missing or invalid checksum.'
if command -v sha256sum >/dev/null 2>&1; then
    actual=$(sha256sum "$temporary/$asset" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
    actual=$(shasum -a 256 "$temporary/$asset" | awk '{print $1}')
else
    fail 'sha256sum or shasum is required.'
fi
[ "$actual" = "$expected" ] || fail 'SHA-256 verification failed; nothing was installed.'
# Extract only the executable: archive paths cannot write outside the temporary directory.
tar -xzf "$temporary/$asset" -C "$temporary" anna
[ -f "$temporary/anna" ] && [ ! -L "$temporary/anna" ] || fail 'Invalid executable in archive.'
chmod 755 "$temporary/anna"
"$temporary/anna" --version
mkdir -p "$install_dir"
[ ! -d "$install_dir/anna" ] || fail 'Destination is a directory.'
# Keep the existing executable intact until the complete replacement is ready.
staged=$(mktemp "$install_dir/.anna-install.XXXXXX")
trap 'rm -rf "$temporary"; rm -f "$staged"' EXIT HUP INT TERM
cp "$temporary/anna" "$staged"
chmod 755 "$staged"
mv -f "$staged" "$install_dir/anna"
printf '%s\n' "Installed $install_dir/anna" >&2
case ":$PATH:" in
    *":$install_dir:"*) ;;
    *) printf '%s\n' "Add $install_dir to PATH to run anna from any directory." >&2 ;;
esac
