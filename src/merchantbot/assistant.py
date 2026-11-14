"""Answers a merchant question from the merchant guide, with optional prompt caching."""
import pathlib
import time
from dataclasses import dataclass, field

from . import config
from .cost import cost_usd

GUIDE = (pathlib.Path(__file__).parent / "data" / "merchant_guide.md").read_text(encoding="utf-8")

INSTRUCTIONS = (
    "You are the merchant-support assistant for an online marketplace. Answer only from the merchant guide below. "
    "Reply in the language the merchant used (Indonesian or English). Keep answers under 120 words. "
    "For fees, discounts, or deadlines, show the calculation or the rule number you used. "
    "If the guide does not cover the question, say so and give the help desk contact."
)


@dataclass
class Call:
    model: str
    text: str
    usage: dict
    latency_ms: int
    extra: dict = field(default_factory=dict)

    @property
    def cost(self) -> float:
        return cost_usd(self.usage, self.model)


def system_blocks(cache: bool) -> list:
    # Everything before the cachePoint is cached: the static instructions and the guide. The
    # question goes in `messages`, AFTER the checkpoint, so it never changes the cached prefix.
    blocks = [{"text": f"{INSTRUCTIONS}\n\n<merchant_guide>\n{GUIDE}\n</merchant_guide>"}]
    if cache:
        blocks.append({"cachePoint": {"type": "default"}})
    return blocks


def answer(brt, question: str, model: str, cache: bool) -> Call:
    t0 = time.perf_counter()
    r = brt.converse(
        modelId=model,
        system=system_blocks(cache),
        messages=[{"role": "user", "content": [{"text": question}]}],
        inferenceConfig={"maxTokens": config.MAX_ANSWER_TOKENS, "temperature": 0},
    )
    text = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
    return Call(model, text, r["usage"], int((time.perf_counter() - t0) * 1000))
