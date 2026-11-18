#!/bin/bash
# Runs every check. Needs python3, node with playwright and acorn, ffprobe.
cd "$(dirname "$0")/.." || exit 1
set -e
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
python3 build.py
python3 tests/test_package.py
python3 tests/test_controller.py
node tests/ui.test.js
echo "ALL CHECKS PASSED"
