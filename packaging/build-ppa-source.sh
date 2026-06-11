#!/usr/bin/env bash
# Build a signed PPA source package from the committed git HEAD.
# Exports tracked files only (no node_modules / build artifacts / local config)
# into a correctly-named dir, then runs debuild -S.
#
# Usage:  packaging/build-ppa-source.sh
# Then:   dput ppa:<you>/<ppa> /tmp/csm-ppa/claude-session-manager_<ver>_source.changes
set -euo pipefail

ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"
ver="$(grep -m1 '^version' "$ROOT/pyproject.toml" | cut -d'"' -f2)"
out="/tmp/csm-ppa"
src="$out/claude-session-manager-$ver"

rm -rf "$out"
mkdir -p "$src"
git -C "$ROOT" archive HEAD | tar -x -C "$src"

cd "$src"
debuild -S -sa

echo
echo "Built in $out:"
ls -1 "$out"/*.changes
