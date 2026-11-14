"""Bedrock Runtime client (or the offline fake), and the prompt-router lookup."""
from botocore.config import Config

from . import config

_client = None
FAKE_ROUTER_ARN = "arn:aws:bedrock:us-east-1:000000000000:default-prompt-router/amazon.nova:1"


def client():
    global _client
    if _client is None:
        if config.FAKE:
            from .fake import FakeBedrock
            _client = FakeBedrock()
        else:
            import boto3
            # Adaptive retries absorb short throttling bursts; the read timeout bounds a slow model call.
            _client = boto3.client("bedrock-runtime", region_name=config.REGION,
                                   config=Config(retries={"mode": "adaptive", "max_attempts": 6},
                                                 connect_timeout=5, read_timeout=60))
    return _client


def ipr_router_arn() -> str:
    """ARN of the Bedrock Intelligent Prompt Routing router used by the `bedrock-ipr` comparison mode.

    IPR_ROUTER_ARN wins; otherwise the default router for the Amazon Nova family in this Region.
    """
    if config.IPR_ROUTER_ARN:
        return config.IPR_ROUTER_ARN
    if config.FAKE:
        return FAKE_ROUTER_ARN
    import boto3
    ctl = boto3.client("bedrock", region_name=config.REGION)
    for page in ctl.get_paginator("list_prompt_routers").paginate(type="default"):
        for r in page["promptRouterSummaries"]:
            if "amazon.nova" in r["promptRouterArn"]:
                return r["promptRouterArn"]
    raise SystemExit(f"No default Amazon Nova prompt router in {config.REGION}. "
                     "Set IPR_ROUTER_ARN, or skip the bedrock-ipr mode.")
