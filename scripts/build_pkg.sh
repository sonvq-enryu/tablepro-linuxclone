#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "build_pkg.sh must run on macOS."
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
BUILD_DIR="$ROOT_DIR/build"

cd "$ROOT_DIR"

PYINSTALLER_CMD=()
if command -v pyinstaller >/dev/null 2>&1; then
  PYINSTALLER_CMD=(pyinstaller)
elif command -v uv >/dev/null 2>&1; then
  PYINSTALLER_CMD=(uv run pyinstaller)
else
  echo "pyinstaller is required. Install it first: pip install pyinstaller"
  exit 1
fi

if ! command -v productbuild >/dev/null 2>&1; then
  echo "productbuild not found. Install Xcode command line tools."
  exit 1
fi

VERSION="$(python3 - <<'PY'
import tomllib
from pathlib import Path
data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

rm -rf "$DIST_DIR" "$BUILD_DIR"
"${PYINSTALLER_CMD[@]}" --noconfirm --clean tablefree.spec

APP_PATH=""
if [[ -d "$DIST_DIR/tablefree.app" ]]; then
  APP_PATH="$DIST_DIR/tablefree.app"
elif [[ -d "$DIST_DIR/tablefree/tablefree.app" ]]; then
  APP_PATH="$DIST_DIR/tablefree/tablefree.app"
else
  echo "Could not find app bundle in dist/."
  exit 1
fi

PKG_NAME="TableFree-${VERSION}.pkg"
PKG_PATH="$DIST_DIR/$PKG_NAME"

PRODUCTBUILD_ARGS=(
  --component "$APP_PATH" /Applications
  --identifier "com.tablefree.app"
  --version "$VERSION"
)

if [[ -n "${INSTALLER_SIGN_IDENTITY:-}" ]]; then
  PRODUCTBUILD_ARGS+=(--sign "$INSTALLER_SIGN_IDENTITY")
fi

productbuild "${PRODUCTBUILD_ARGS[@]}" "$PKG_PATH"
echo "Created $PKG_PATH"
