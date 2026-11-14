"""One request end to end, in one of the modes used by the experiment."""
from . import assistant, bedrock, config, router

MODES = {
    # mode: (our router on, prompt caching on)
    "baseline": (False, False),
    "cache": (False, True),
    "router": (True, False),
    "router-cache": (True, True),
    # Comparison: Amazon Bedrock Intelligent Prompt Routing (default Nova router: Nova Lite / Nova Pro)
    # instead of our router. No prompt caching, so compare it with `router`.
    "bedrock-ipr": (None, False),
}


def ask(brt, question: str, use_router, use_cache: bool) -> dict:
    if use_router is None:
        return ask_ipr(brt, question)
    d = router.route(brt, question, enabled=use_router)
    a = assistant.answer(brt, question, d.model, cache=use_cache)
    router_cost = d.call.cost if d.call else 0.0
    return {
        "answer": a.text,
        "model": a.model,
        "route": d.label,
        "route_reason": d.reason,
        "small_model": a.model == config.SMALL_MODEL,
        "usage": a.usage,
        "router_usage": d.call.usage if d.call else None,
        "answer_cost_usd": a.cost,
        "router_cost_usd": router_cost,
        "cost_usd": a.cost + router_cost,
        "latency_ms": a.latency_ms + (d.call.latency_ms if d.call else 0),
    }


def ask_ipr(brt, question: str) -> dict:
    """Same question through Bedrock's managed router. The trace says which model answered."""
    a = assistant.answer(brt, question, bedrock.ipr_router_arn(), cache=False)
    cheap = "nova-lite" in a.model  # the default Nova router picks Nova Lite or Nova Pro
    return {
        "answer": a.text,
        "model": a.model.rsplit("/", 1)[-1],
        "route": "simple" if cheap else "complex",
        "route_reason": "bedrock-ipr",
        "small_model": cheap,
        "usage": a.usage,
        "router_usage": None,
        "answer_cost_usd": a.cost,   # Bedrock does not bill the routing step separately (check the pricing page)
        "router_cost_usd": 0.0,
        "cost_usd": a.cost,
        "latency_ms": a.latency_ms,
    }
