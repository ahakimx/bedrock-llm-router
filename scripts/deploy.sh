#!/usr/bin/env bash
# Builds and deploys the Lambda assistant with AWS SAM.
set -euo pipefail
cd "$(dirname "$0")/.."
STACK="${STACK:-merchant-assistant}"
REGION="${AWS_REGION:-us-east-1}"
sam build --template-file infra/template.yaml
sam deploy --stack-name "$STACK" --region "$REGION" --resolve-s3 \
  --capabilities CAPABILITY_IAM --no-confirm-changeset --no-fail-on-empty-changeset
aws cloudformation describe-stacks --stack-name "$STACK" --region "$REGION" \
  --query "Stacks[0].Outputs" --output table
