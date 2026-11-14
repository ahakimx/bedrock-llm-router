#!/usr/bin/env bash
# Usage: scripts/ask.sh "Berapa minimal penarikan saldo?"
set -euo pipefail
STACK="${STACK:-merchant-assistant}"
REGION="${AWS_REGION:-us-east-1}"
payload=$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1]}))' "$1")
out=$(mktemp)
trap 'rm -f "$out"' EXIT
# The function's response goes to $out; the invoke metadata (StatusCode, ...) is not printed.
aws lambda invoke --function-name "$STACK-assistant" --region "$REGION" \
  --cli-binary-format raw-in-base64-out --payload "$payload" "$out" > /dev/null
python3 -m json.tool --no-ensure-ascii "$out"
