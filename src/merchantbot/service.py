"""One request end to end, in one of four modes used by the experiment."""
from . import assistant, config, router

MODES = {
    # mode: (router on, prompt caching on)
    "baseline": (False, False),
    "cache": (False, True),
    "router": (True, False),
    "router-cache": (True, True),
}


def ask(brt, question: str, use_router: bool, use_cache: bool) -> dict:
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
