#!/usr/bin/env bash
# Usage: scripts/ask.sh "What is the minimum withdrawal?"
set -euo pipefail
STACK="${STACK:-lapak-assistant}"
REGION="${AWS_REGION:-us-east-1}"
payload=$(python3 -c 'import json,sys; print(json.dumps({"question": sys.argv[1]}))' "$1")
aws lambda invoke --function-name "$STACK-assistant" --region "$REGION" \
  --cli-binary-format raw-in-base64-out --payload "$payload" /dev/stdout | python3 -m json.tool
