#!/usr/bin/env sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <version>" >&2
  echo "Example: $0 0.1.1" >&2
  exit 1
fi

VERSION="$1"
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+(\.[0-9]+)*$'; then
  echo "Invalid version: $VERSION" >&2
  echo "Use a numeric dotted version such as 0.1.1 or 1.0.0" >&2
  exit 1
fi

TAG="v$VERSION"
PKGNAME="tidal-cli-client-python"
AUR_REMOTE_URL="ssh://aur@aur.archlinux.org/${PKGNAME}.git"

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
AUR_DIR="$REPO_ROOT/packaging/aur"
AUR_TMP_DIR="/tmp/aur-${PKGNAME}"

for cmd in git makepkg updpkgsums; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing required command: $cmd" >&2
    exit 1
  fi
done

if [ ! -f "$AUR_DIR/PKGBUILD" ] || [ ! -f "$AUR_DIR/.SRCINFO" ]; then
  echo "Expected AUR files in $AUR_DIR" >&2
  exit 1
fi

cd "$REPO_ROOT"

if [ -n "$(git status --porcelain)" ]; then
  echo "Working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" = "HEAD" ]; then
  echo "Detached HEAD is not supported for release." >&2
  exit 1
fi

if git rev-parse "$TAG" >/dev/null 2>&1; then
  echo "Warning: local tag $TAG already exists. Re-creating it." >&2
  git tag -d "$TAG"
fi

# Also delete the remote tag if it already exists, so the push later doesn't fail.
if git ls-remote --tags origin "refs/tags/$TAG" | grep -q "$TAG"; then
  echo "Warning: remote tag $TAG already exists. Deleting from origin." >&2
  git push origin ":refs/tags/$TAG"
fi

# Step 1: bump pkgver in PKGBUILD only — do NOT run updpkgsums yet because
# the GitHub tarball won't exist until the tag is pushed.
echo "Bumping pkgver in PKGBUILD to $VERSION..."
TMP_PKGBUILD="$AUR_DIR/PKGBUILD.tmp"
awk -v v="$VERSION" '
  BEGIN { replaced = 0 }
  /^pkgver=/ { print "pkgver=" v; replaced = 1; next }
  { print }
  END { if (replaced == 0) { print "Failed to find pkgver= line" > "/dev/stderr"; exit 1 } }
' "$AUR_DIR/PKGBUILD" > "$TMP_PKGBUILD"
mv "$TMP_PKGBUILD" "$AUR_DIR/PKGBUILD"
echo "Updated pkgver to $VERSION"

if [ -n "$(git status --porcelain packaging/aur/PKGBUILD)" ]; then
  git add packaging/aur/PKGBUILD
  git commit -m "release: $TAG (version bump)"
fi

echo "Pushing branch $CURRENT_BRANCH to origin..."
git push origin "$CURRENT_BRANCH"

# Step 2: create and push the tag so the tarball becomes available on GitHub.
echo "Creating and pushing tag $TAG..."
git tag "$TAG"
git push origin "$TAG"

# Step 3: now that the tarball exists, compute checksums and regenerate .SRCINFO.
echo "Computing checksums (tarball is now live on GitHub)..."
cd "$AUR_DIR"
updpkgsums
makepkg --printsrcinfo > .SRCINFO
cd "$REPO_ROOT"

if [ -n "$(git status --porcelain packaging/aur/PKGBUILD packaging/aur/.SRCINFO)" ]; then
  git add packaging/aur/PKGBUILD packaging/aur/.SRCINFO
  git commit -m "release: $TAG checksums"
  git push origin "$CURRENT_BRANCH"
fi

echo "Publishing PKGBUILD/.SRCINFO to AUR..."
rm -rf "$AUR_TMP_DIR"
git clone "$AUR_REMOTE_URL" "$AUR_TMP_DIR"
cp "$AUR_DIR/PKGBUILD" "$AUR_DIR/.SRCINFO" "$AUR_TMP_DIR/"

cd "$AUR_TMP_DIR"
if [ -n "$(git status --porcelain PKGBUILD .SRCINFO)" ]; then
  git add PKGBUILD .SRCINFO
  git commit -m "release: $TAG"
  git push
  echo "AUR updated: $PKGNAME ($TAG)"
else
  echo "No AUR changes detected; nothing to push."
fi

echo "Release completed for $TAG"
