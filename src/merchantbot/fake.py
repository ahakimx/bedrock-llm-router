"""Offline stand-in for bedrock-runtime, used by tests and by FAKE_BEDROCK=1.

It is NOT a model. Answers are built from the golden dataset so the whole pipeline (routing,
caching, grading, cost, report) can be exercised without AWS. To mimic a weaker small model, the
small model "gets wrong" every complex question routed to it. Numbers from this mode are not results.
"""
import json
import pathlib
import time

_GOLDEN = {json.loads(l)["question"]: json.loads(l)
           for l in (pathlib.Path(__file__).resolve().parents[2] / "data" / "golden.jsonl").read_text().splitlines() if l}


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


class FakeBedrock:
    def __init__(self, cache_ttl_s: float = 300):
        self.cache = {}           # (model, prefix) -> expiry
        self.ttl = cache_ttl_s
        self.calls = 0

    def converse(self, modelId, system, messages, inferenceConfig, toolConfig=None):
        self.calls += 1
        q = messages[0]["content"][0]["text"]
        if toolConfig:  # router call
            hard = self._hard(q)
            label = "complex" if hard else "simple"
            return {"output": {"message": {"content": [{"toolUse": {"name": "route", "input": {"label": label}}}]}},
                    "usage": {"inputTokens": _tokens(system[0]["text"] + q) + 120, "outputTokens": 12}}
        g = _GOLDEN.get(q, {"expect": [], "label": "complex"})
        trace = None
        if ":default-prompt-router/" in modelId or ":prompt-router/" in modelId:
            # Fake managed router: picks the cheaper model for short questions only (a different heuristic
            # from ours, so the comparison is not trivially identical).
            picked = "us.amazon.nova-lite-v1:0" if len(q) < 60 else "us.amazon.nova-pro-v1:0"
            trace = {"promptRouter": {"invokedModelId": f"arn:aws:bedrock:us-east-1:000000000000:inference-profile/{picked}"}}
            modelId = picked
        small = "micro" in modelId or "nova-lite-v1" in modelId
        if small and g["label"] == "complex":
            text = "Sorry, I am not sure."  # the fake small model fails complex questions
        else:
            text = "Answer: " + "; ".join(group[0] for group in g["expect"])
        prefix = system[0]["text"]
        usage = {"outputTokens": _tokens(text)}
        cached = any("cachePoint" in b for b in system)
        if cached:
            key = (modelId, prefix)
            if self.cache.get(key, 0) > time.time():
                usage["cacheReadInputTokens"] = _tokens(prefix)
            else:
                usage["cacheWriteInputTokens"] = _tokens(prefix)
            self.cache[key] = time.time() + self.ttl
            usage["inputTokens"] = _tokens(q)
        else:
            usage["inputTokens"] = _tokens(prefix + q)
        r = {"output": {"message": {"content": [{"text": text}]}}, "usage": usage}
        if trace:
            r["trace"] = trace
        return r

    @staticmethod
    def _hard(q: str) -> bool:
        return any(w in q.lower() for w in ("rp", "tidak adil", "apa yang terjadi", "apa akibatnya", "kapan uangnya",
                                            "siapa yang bayar", "langsung tarik", "voucher", "kota tetangga",
                                            "30 jam", "wajib menerima"))
