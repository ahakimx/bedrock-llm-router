"""Small-model router: classify a question as simple or complex, then pick the answering model."""
import logging
import time
from dataclasses import dataclass
from typing import Optional

from . import config
from .assistant import Call

log = logging.getLogger(__name__)

ROUTER_SYSTEM = (
    "You route questions from marketplace merchants. The questions are in Indonesian. "
    "Call the `route` tool exactly once.\n"
    "simple = the answer is one fact or one rule from a policy (a number, a yes/no, a time, a limit).\n"
    "complex = anything that needs a calculation, combines two or more rules, depends on a date or day of the "
    "week, handles a complaint or an angry merchant, or might not be covered by the policy at all.\n"
    "When unsure, choose complex.\n"
    # Examples are deliberately NOT taken from data/golden.jsonl, so the evaluation stays honest.
    "Examples: 'Berapa lama moderasi produk?' = simple. "
    "'Saya tarik saldo ke BCA dua kali hari ini, total biayanya berapa?' = complex."
)

ROUTE_TOOL = {"toolSpec": {
    "name": "route",
    "description": "Record how hard the merchant question is.",
    "inputSchema": {"json": {
        "type": "object",
        "properties": {"label": {"type": "string", "enum": ["simple", "complex"]}},
        "required": ["label"],
    }},
}}


@dataclass
class Decision:
    label: str               # simple | complex
    model: str               # model that will answer
    reason: str              # classified | router-off | router-error
    call: Optional[Call]     # the router's own model call (None when skipped)


def classify(brt, question: str) -> Call:
    t0 = time.perf_counter()
    r = brt.converse(
        modelId=config.ROUTER_MODEL,
        system=[{"text": ROUTER_SYSTEM}],
        messages=[{"role": "user", "content": [{"text": question}]}],
        toolConfig={"tools": [ROUTE_TOOL], "toolChoice": {"tool": {"name": "route"}}},
        inferenceConfig={"maxTokens": 30, "temperature": 0},
    )
    label = next(b["toolUse"]["input"]["label"] for b in r["output"]["message"]["content"] if "toolUse" in b)
    if label not in ("simple", "complex"):
        raise ValueError(f"unexpected label {label!r}")
    return Call(config.ROUTER_MODEL, label, r["usage"], int((time.perf_counter() - t0) * 1000))


def route(brt, question: str, enabled: bool = True) -> Decision:
    if not enabled:
        return Decision("complex", config.PRIMARY_MODEL, "router-off", None)
    try:
        c = classify(brt, question)
    except Exception:  # noqa: BLE001 - any router failure must fall back, never fail the request
        log.exception("router failed, falling back to the primary model")
        return Decision("complex", config.PRIMARY_MODEL, "router-error", None)
    model = config.SMALL_MODEL if c.text == "simple" else config.PRIMARY_MODEL
    return Decision(c.text, model, "classified", c)
