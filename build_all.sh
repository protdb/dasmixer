#!/usr/bin/env bash
#
# build_all.sh — Сборка и публикация всех пакетов DASMixer
#
# Использование:
#   ./build_all.sh              # Собрать все пакеты
#   ./build_all.sh --skip-build # Только публикация (если dist уже есть)
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PACKAGES=("dasmixer-core" "dasmixer-gui" "dasmixer-cli" "metapackage")

echo "=== DASMixer Build Script ==="
echo ""

# ---------------------------------------------------------------------------
# Проверка зависимостей
# ---------------------------------------------------------------------------
command -v poetry >/dev/null 2>&1 || { echo "ERROR: poetry not found. Install it first."; exit 1; }
command -v twine  >/dev/null 2>&1 || { echo "ERROR: twine not found. pip install twine"; exit 1; }

# ---------------------------------------------------------------------------
# Сборка
# ---------------------------------------------------------------------------
ALL_DISTS=()

if [[ "${1:-}" != "--skip-build" ]]; then
    for pkg in "${PACKAGES[@]}"; do
        PKG_DIR="$REPO_ROOT/$pkg"
        echo "--- Building $pkg ---"
        (cd "$PKG_DIR" && poetry build)
        echo ""
    done

    # Collect all dist artifacts
    while IFS= read -r f; do
        ALL_DISTS+=("$f")
    done < <(find "$REPO_ROOT/dasmixer-core/dist" \
                  "$REPO_ROOT/dasmixer-gui/dist" \
                  "$REPO_ROOT/dasmixer-cli/dist" \
                  "$REPO_ROOT/metapackage/dist" \
                  -name "*.whl" -o -name "*.tar.gz" 2>/dev/null)

    if [ ${#ALL_DISTS[@]} -eq 0 ]; then
        echo "No build artifacts found. Something went wrong."
        exit 1
    fi

    echo ""
    echo "=== Built artifacts ==="
    for f in "${ALL_DISTS[@]}"; do
        echo "  $f"
    done
    echo ""
else
    while IFS= read -r f; do
        ALL_DISTS+=("$f")
    done < <(find "$REPO_ROOT/dasmixer-core/dist" \
                  "$REPO_ROOT/dasmixer-gui/dist" \
                  "$REPO_ROOT/dasmixer-cli/dist" \
                  "$REPO_ROOT/metapackage/dist" \
                  -name "*.whl" -o -name "*.tar.gz" 2>/dev/null)
fi

# ---------------------------------------------------------------------------
# Загрузка на TestPyPI
# ---------------------------------------------------------------------------
read -rp "Upload to TestPyPI? [y/N] " confirm
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    twine upload --repository testpypi "${ALL_DISTS[@]}"
    echo ""
    echo "=== TestPyPI links ==="
    for pkg in "${PACKAGES[@]}"; do
        echo "  https://test.pypi.org/project/$pkg/"
    done
    echo ""
fi

# ---------------------------------------------------------------------------
# Загрузка на PyPI (production)
# ---------------------------------------------------------------------------
read -rp "Upload to PyPI (PRODUCTION)? [y/N] " confirm2
if [[ "$confirm2" =~ ^[Yy]$ ]]; then
    twine upload "${ALL_DISTS[@]}"
    echo "Done."
fi