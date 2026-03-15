#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"
PKG_ROOT="$ROOT_DIR/pkg-deb"

cd "$ROOT_DIR"

cleanup() {
  rm -rf "$PKG_ROOT"
}
trap cleanup EXIT

PYINSTALLER_CMD=()
if command -v pyinstaller >/dev/null 2>&1; then
  PYINSTALLER_CMD=(pyinstaller)
elif command -v uv >/dev/null 2>&1; then
  PYINSTALLER_CMD=(uv run pyinstaller)
else
  echo "pyinstaller is required. Install it first: pip install pyinstaller"
  exit 1
fi

VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"
ARCH="$(dpkg --print-architecture)"

rm -rf "$DIST_DIR" "$BUILD_DIR" "$PKG_ROOT"
"${PYINSTALLER_CMD[@]}" --noconfirm --clean tablefree.spec

mkdir -p "$PKG_ROOT/DEBIAN"
mkdir -p "$PKG_ROOT/usr/bin"
mkdir -p "$PKG_ROOT/usr/share/tablefree"
mkdir -p "$PKG_ROOT/usr/share/applications"
mkdir -p "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps"

cp -a "$DIST_DIR/tablefree/." "$PKG_ROOT/usr/share/tablefree/"
ln -s ../share/tablefree/tablefree "$PKG_ROOT/usr/bin/tablefree"

cp "$ROOT_DIR/packaging/deb/tablefree.desktop" \
  "$PKG_ROOT/usr/share/applications/tablefree.desktop"

APP_ICON="$ROOT_DIR/resources/icons/app_icon.png"
if [[ -f "$APP_ICON" ]]; then
  cp "$APP_ICON" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/tablefree.png"
fi

sed -e "s/__VERSION__/$VERSION/g" -e "s/__ARCH__/$ARCH/g" \
  "$ROOT_DIR/packaging/deb/control" > "$PKG_ROOT/DEBIAN/control"

chmod 0755 "$PKG_ROOT/usr/share/tablefree/tablefree"
chmod 0644 "$PKG_ROOT/DEBIAN/control"

OUTPUT_NAME="tablefree_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$DIST_DIR/$OUTPUT_NAME"

echo "Created $DIST_DIR/$OUTPUT_NAME"
