"""AWS Lambda entry point: {"question": "..."} -> answer, with per-request cost metrics.

Writes one CloudWatch Embedded Metric Format (EMF) line per request, so cost, latency, route, and
router fallbacks become CloudWatch metrics without any extra API call.
"""
import json
import logging
import time

from . import bedrock, config
from .service import ask

logging.getLogger().setLevel(logging.INFO)
_flag = {"value": {"router": True, "cache": True}, "expires": 0.0}


def flags() -> dict:
    """Read the feature flag from SSM at most once a minute (container reuse keeps the cache)."""
    if not config.FLAG_PARAM or config.FAKE:
        return _flag["value"]
    if time.time() > _flag["expires"]:
        import boto3
        try:
            raw = boto3.client("ssm", region_name=config.REGION).get_parameter(Name=config.FLAG_PARAM)["Parameter"]["Value"]
            _flag["value"] = {"router": True, "cache": True, **json.loads(raw)}
        except Exception:  # noqa: BLE001 - keep the last known flags if SSM is unavailable
            logging.exception("could not read %s, keeping %s", config.FLAG_PARAM, _flag["value"])
        _flag["expires"] = time.time() + 60
    return _flag["value"]


def emf(r: dict) -> str:
    return json.dumps({
        "_aws": {"Timestamp": int(time.time() * 1000), "CloudWatchMetrics": [{
            "Namespace": "MerchantAssistant",
            "Dimensions": [["Route"]],
            "Metrics": [{"Name": "CostUSD", "Unit": "None"}, {"Name": "LatencyMs", "Unit": "Milliseconds"},
                        {"Name": "CacheReadTokens", "Unit": "Count"}, {"Name": "RouterFallback", "Unit": "Count"}],
        }]},
        "Route": r["route"] if r["route_reason"] == "classified" else r["route_reason"],
        "CostUSD": r["cost_usd"],
        "LatencyMs": r["latency_ms"],
        "CacheReadTokens": r["usage"].get("cacheReadInputTokens", 0),
        "RouterFallback": int(r["route_reason"] == "router-error"),
        "model": r["model"],          # properties (not dimensions): searchable in Logs Insights, no extra metric cost
        "inputTokens": r["usage"].get("inputTokens", 0),
        "outputTokens": r["usage"].get("outputTokens", 0),
    })


def handler(event, context):
    question = (event or {}).get("question", "").strip()
    if not question or len(question) > 2000:
        return {"statusCode": 400, "error": "question is required (max 2000 characters)"}
    f = flags()
    r = ask(bedrock.client(), question, use_router=f["router"], use_cache=f["cache"])
    print(emf(r))
    return {"statusCode": 200, "answer": r["answer"], "route": r["route"], "model": r["model"],
            "cost_usd": round(r["cost_usd"], 8), "latency_ms": r["latency_ms"]}
