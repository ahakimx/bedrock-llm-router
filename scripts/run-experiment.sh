#!/usr/bin/env bash
# Runs the 30-question golden dataset through every mode against Amazon Bedrock, then prints the
# comparison table. Cost: well under US$0.20 in total. Needs AWS credentials and model access (see README).
#   SKIP_IPR=1 scripts/run-experiment.sh   # skip the Bedrock Intelligent Prompt Routing comparison
set -euo pipefail
cd "$(dirname "$0")/.."
export AWS_REGION="${AWS_REGION:-us-east-1}"
export PYTHONPATH=src
for mode in baseline router cache router-cache; do
  echo "== $mode"
  python3 -m merchantbot.evaluate --mode "$mode" > /dev/null
done
if [ "${SKIP_IPR:-0}" != "1" ]; then
  echo "== bedrock-ipr (comparison: Bedrock Intelligent Prompt Routing, Nova Lite / Nova Pro)"
  python3 -m merchantbot.evaluate --mode bedrock-ipr > /dev/null \
    || echo "   bedrock-ipr failed (no default Nova prompt router or no Nova Lite/Pro access?); continuing without it"
fi
python3 -m merchantbot.report | tee results/report.md
