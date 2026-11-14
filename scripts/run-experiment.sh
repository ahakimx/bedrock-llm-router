#!/usr/bin/env bash
# Runs the 30-question golden dataset through all four modes against Amazon Bedrock, then prints the
# comparison table. Cost: a few US cents in total. Needs AWS credentials and model access (see README).
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION="${AWS_REGION:-us-east-1}"
export PYTHONPATH=src
for mode in baseline router cache router-cache; do
  echo "== $mode"
  python3 -m lapak.evaluate --mode "$mode" > /dev/null
done
python3 -m lapak.report | tee results/report.md
