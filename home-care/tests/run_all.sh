#!/bin/bash
cd /home/claude/hack
export NODE_PATH=$(npm root -g):/tmp/claude-0/-home-claude/b05a1f0c-dd7e-5d57-999d-12aa7eb13b58/scratchpad/jsdeps/node_modules
python3 tests/test_xar.py 2>&1 | tail -2 && 
python3 tests/test_controller.py 2>&1 | tail -3 && python3 tests/test_dialog.py 2>&1 | tail -2 &&
