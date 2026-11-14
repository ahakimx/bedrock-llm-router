#!/usr/bin/env bash
# Deletes everything the stack created (function, log group, SSM parameter, alarm, IAM role)
# and the SAM artifact bucket objects for this stack.
set -euo pipefail
STACK="${STACK:-merchant-assistant}"
REGION="${AWS_REGION:-us-east-1}"
sam delete --stack-name "$STACK" --region "$REGION" --no-prompts
echo "Stack $STACK deleted. Local results/ are kept; delete them with: rm -rf results/*"
