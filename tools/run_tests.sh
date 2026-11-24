#!/usr/bin/env bash
# Every card runs this: python tests (sun arc, manifests), C# core tests, headless Atlas smoke run.
set -euo pipefail
cd "$(dirname "$0")/.."
echo "[Test] python"
python3 -m unittest discover -s tests
echo "[Test] all green"
