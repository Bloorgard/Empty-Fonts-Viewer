#!/usr/bin/env bash
#
# release.sh — package and publish a new VTF Viewer release.
#
# Workflow:
#   1. In Glyphs, export OTF + WOFF + WOFF2 and save the .glyphs source
#      into this repository folder (the export names may include a version,
#      e.g. VTFViewer_v0.009-Regular.otf and VTF_Viewer_v0.009.glyphs).
#   2. Run:  ./release.sh            (version is read from the source name)
#      or:    ./release.sh 0.009     (force a version explicitly)
#
# The script normalises file names, updates sources/ and fonts/, commits,
# tags vX.Y.Z, and publishes a GitHub Release with a zipped font package.
# It asks for confirmation before anything is pushed to GitHub.

set -euo pipefail

FAMILY="VTFViewer"          # stable file basename -> VTFViewer-Regular.otf
STYLE="Regular"
cd "$(dirname "$0")"

say()  { printf '\033[1;36m%s\033[0m\n' "$*"; }
warn() { printf '\033[1;33m%s\033[0m\n' "$*"; }
die()  { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

# --- 1. locate the source .glyphs (freshly dropped in root wins) -------------
SRC="$(ls -t ./*.glyphs sources/*.glyphs 2>/dev/null | head -n1 || true)"
[ -n "$SRC" ] || die "No .glyphs source found in repo root or sources/."
say "Source: $SRC"

# --- 2. determine version ----------------------------------------------------
if [ "${1:-}" != "" ]; then
  VERSION="$1"
else
  VERSION="$(basename "$SRC" | sed -nE 's/.*_v([0-9]+\.[0-9]+).*\.glyphs/\1/p')"
fi
[ -n "$VERSION" ] || die "Could not read version. Pass it explicitly: ./release.sh 0.009"
TAG="v$VERSION"
say "Version: $VERSION  (tag $TAG)"

git rev-parse "$TAG" >/dev/null 2>&1 && die "Tag $TAG already exists."

# --- 3. normalise source into sources/ --------------------------------------
mkdir -p sources fonts dist
if [ "$(dirname "$SRC")" != "sources" ]; then
  git rm -q sources/*.glyphs 2>/dev/null || rm -f sources/*.glyphs
  DEST="sources/$(basename "$SRC")"
  mv -f "$SRC" "$DEST"
  SRC="$DEST"
fi

# --- 4. normalise exported fonts into fonts/ --------------------------------
for EXT in otf woff woff2; do
  DEST="fonts/${FAMILY}-${STYLE}.${EXT}"
  NEW="$(ls -t ./*-${STYLE}.${EXT} 2>/dev/null | head -n1 || true)"   # freshly exported in root
  if [ -n "$NEW" ] && [ "$NEW" != "$DEST" ]; then
    mv -f "$NEW" "$DEST"
    say "  fonts/${FAMILY}-${STYLE}.${EXT}  <- $(basename "$NEW")"
  fi
  [ -f "$DEST" ] || die "Missing $DEST — export the $EXT from Glyphs first."
done

# --- 5. build the release zip ------------------------------------------------
ZIP="dist/${FAMILY}-${TAG}.zip"
rm -f "$ZIP"
TMP="dist/${FAMILY}-${TAG}"
rm -rf "$TMP"; mkdir -p "$TMP"
cp fonts/${FAMILY}-${STYLE}.otf fonts/${FAMILY}-${STYLE}.woff fonts/${FAMILY}-${STYLE}.woff2 \
   LICENSE FONTLOG.txt README.md "$TMP"/
( cd dist && zip -qr "${FAMILY}-${TAG}.zip" "${FAMILY}-${TAG}" )
rm -rf "$TMP"
say "Package: $ZIP"

# --- 6. commit + tag ---------------------------------------------------------
git add -A
if git diff --cached --quiet; then
  warn "Nothing changed in tracked files."
else
  git commit -q -m "Release $TAG"
  say "Committed: Release $TAG"
fi
git tag -a "$TAG" -m "VTF Viewer $TAG"

# --- 7. push + publish (with confirmation) ----------------------------------
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
printf '\n'
read -r -p "Push branch '$BRANCH' + tag '$TAG' and publish the GitHub Release? [y/N] " ans
if [[ "${ans:-}" =~ ^[Yy]$ ]]; then
  git push origin "$BRANCH"
  git push origin "$TAG"
  gh release create "$TAG" "$ZIP" \
    --title "VTF Viewer $TAG" \
    --generate-notes
  say "Published: https://github.com/Bloorgard/Empty-Fonts-Viewer/releases/tag/$TAG"
else
  warn "Stopped before pushing. Local commit and tag $TAG are ready."
  warn "To undo the tag:   git tag -d $TAG"
fi
