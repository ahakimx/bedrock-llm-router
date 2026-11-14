"""Bedrock Runtime client (or the offline fake)."""
from botocore.config import Config

from . import config

_client = None


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
