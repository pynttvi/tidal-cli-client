#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
AUR_DIR="$REPO_ROOT/packaging/aur"
PKGBUILD="$AUR_DIR/PKGBUILD"

if [ ! -f "$PKGBUILD" ]; then
  echo "PKGBUILD not found at $PKGBUILD" >&2
  exit 1
fi

if ! command -v updpkgsums >/dev/null 2>&1; then
  echo "updpkgsums is required (pacman-contrib)." >&2
  exit 1
fi

if ! command -v makepkg >/dev/null 2>&1; then
  echo "makepkg is required (base-devel)." >&2
  exit 1
fi

NEW_VERSION="${1:-}"

if [ -n "$NEW_VERSION" ]; then
  if ! printf '%s' "$NEW_VERSION" | grep -Eq '^[0-9]+(\.[0-9]+)*$'; then
    echo "Invalid version: $NEW_VERSION" >&2
    echo "Use a numeric dotted version such as 0.1.1 or 1.0.0" >&2
    exit 1
  fi

  TMP_FILE="$PKGBUILD.tmp"
  awk -v v="$NEW_VERSION" '
    BEGIN { replaced = 0 }
    /^pkgver=/ {
      print "pkgver=" v
      replaced = 1
      next
    }
    { print }
    END {
      if (replaced == 0) {
        print "Failed to find pkgver= line" > "/dev/stderr"
        exit 1
      }
    }
  ' "$PKGBUILD" > "$TMP_FILE"
  mv "$TMP_FILE" "$PKGBUILD"
  echo "Updated pkgver to $NEW_VERSION"
fi

cd "$AUR_DIR"
updpkgsums
makepkg --printsrcinfo > .SRCINFO

echo "AUR metadata updated:"
echo "- $PKGBUILD"
echo "- $AUR_DIR/.SRCINFO"
