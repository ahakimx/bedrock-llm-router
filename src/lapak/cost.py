"""Token usage -> USD, using data/pricing.json."""
import json
import pathlib

_PRICES = json.loads((pathlib.Path(__file__).parent / "data" / "pricing.json").read_text())


def base_model(model_id: str) -> str:
    """us.amazon.nova-micro-v1:0 -> amazon.nova-micro-v1:0 (profiles are priced like the base model)."""
    for prefix in ("global.", "us.", "eu.", "apac.", "jp.", "au."):
        if model_id.startswith(prefix):
            return model_id[len(prefix):]
    return model_id


def prices(model_id: str) -> dict:
    try:
        return _PRICES[base_model(model_id)]
    except KeyError:
        raise KeyError(f"No price for {model_id}. Add it to src/lapak/data/pricing.json") from None


def cost_usd(usage: dict, model_id: str) -> float:
    """Converse usage -> USD. inputTokens excludes cached tokens; cache reads/writes are separate fields."""
    p = prices(model_id)
    return (
        usage.get("inputTokens", 0) * p["input"]
        + usage.get("outputTokens", 0) * p["output"]
        + usage.get("cacheReadInputTokens", 0) * p["cache_read"]
        + usage.get("cacheWriteInputTokens", 0) * p["cache_write"]
    ) / 1_000_000
