#!/usr/bin/env bash
set -euo pipefail

# Resolve project root: script lives in <root>/tests/
PROJECT_ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=== Building ==="
cargo build

echo ""
echo "=== Compiling test shared libraries ==="
python3 tests/scripts/test-scripts/compile_lib.py \
    tests/lib/src tests/lib

echo ""
echo "=== Running tests (single-threaded to avoid /tmp/test.o races) ==="
cargo test -- --test-threads=1
