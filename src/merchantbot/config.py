"""Settings, all overridable with environment variables."""
import os

REGION = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"

# Cross-Region inference profiles (US geography). The "us." prefix lets Bedrock serve the request
# from us-east-1, us-east-2 or us-west-2, which matters for prompt caching (see README).
PRIMARY_MODEL = os.environ.get("PRIMARY_MODEL", "us.amazon.nova-2-lite-v1:0")
SMALL_MODEL = os.environ.get("SMALL_MODEL", "us.amazon.nova-micro-v1:0")
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", SMALL_MODEL)

# Optional comparison: Amazon Bedrock Intelligent Prompt Routing. Leave empty to use the default
# router for the Amazon Nova family in your account and Region (looked up at run time).
IPR_ROUTER_ARN = os.environ.get("IPR_ROUTER_ARN", "")

MAX_ANSWER_TOKENS = int(os.environ.get("MAX_ANSWER_TOKENS", "300"))

# Lambda only: SSM parameter that holds {"router": true, "cache": true}. Lets you switch the
# router off in production without a deploy.
FLAG_PARAM = os.environ.get("ROUTER_FLAG_PARAM", "")

# FAKE_BEDROCK=1 runs everything against an offline fake (no AWS calls, no cost). For tests only.
FAKE = os.environ.get("FAKE_BEDROCK") == "1"
