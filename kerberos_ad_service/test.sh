#!/usr/bin/env bash
set -euo pipefail

python -m pytest tests/unit -q
python -m pytest tests/integration -q
bash tests/smoke/smoke_test.sh

echo "All tests passed."
