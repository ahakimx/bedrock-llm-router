"""Offline tests: no AWS calls. Run with `FAKE_BEDROCK=1 python -m pytest -q` from the repo root."""
import os
import sys
import pathlib

os.environ["FAKE_BEDROCK"] = "1"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from merchantbot import assistant, config, cost, evaluate, handler, router  # noqa: E402
from merchantbot.fake import FakeBedrock  # noqa: E402
from merchantbot.grading import grade, normalize  # noqa: E402


def test_number_normalization():
    assert normalize("Rp50.000") == normalize("rp 50,000") == "rp50000"
    assert "50000" in normalize("Rp50.000")
    assert "1000000" in normalize("Rp1.000.000")
    assert "20.00" in normalize("until 20.00 WIB")       # a time, not a thousands separator


def test_grade_needs_every_group():
    expect = [["24"], ["hold", "wait"]]
    assert grade("You must wait 24 hours.", expect)
    assert not grade("Yes, withdraw now.", expect)


def test_cost_uses_cache_prices():
    usage = {"inputTokens": 1_000_000, "outputTokens": 0, "cacheReadInputTokens": 1_000_000}
    p = cost.prices("us.amazon.nova-2-lite-v1:0")
    assert cost.cost_usd(usage, "us.amazon.nova-2-lite-v1:0") == p["input"] + p["cache_read"]


def test_question_is_after_the_cache_point():
    blocks = assistant.system_blocks(cache=True)
    assert blocks[-1] == {"cachePoint": {"type": "default"}}
    assert "<merchant_guide>" in blocks[0]["text"]
    # the guide must be long enough to be cached (Amazon Nova: at least ~1K tokens before a checkpoint)
    assert len(blocks[0]["text"]) / 4 > 1500


def test_router_falls_back_when_the_router_fails():
    class Broken(FakeBedrock):
        def converse(self, **kw):
            if kw.get("toolConfig"):
                raise RuntimeError("ThrottlingException")
            return super().converse(**kw)

    d = router.route(Broken(), "What is the minimum withdrawal?")
    assert (d.model, d.reason, d.call) == (config.PRIMARY_MODEL, "router-error", None)


def test_router_sends_simple_questions_to_the_small_model():
    d = router.route(FakeBedrock(), "What is the minimum amount I can withdraw from my balance?")
    assert (d.label, d.model) == ("simple", config.SMALL_MODEL)


def test_misrouted_complex_question_fails_quality(tmp_path):
    # The fake small model cannot answer complex questions: a misroute must show up as a failed answer.
    from merchantbot.service import ask
    q = "My store score has been 55 for the last two weeks. What happens to my store?"

    class AlwaysSimple(FakeBedrock):
        def converse(self, **kw):
            r = super().converse(**kw)
            if kw.get("toolConfig"):
                r["output"]["message"]["content"][0]["toolUse"]["input"]["label"] = "simple"
            return r

    r = ask(AlwaysSimple(), q, use_router=True, use_cache=False)
    assert r["small_model"] and not grade(r["answer"], [["campaign"]])


def test_all_modes_end_to_end(tmp_path):
    out = {m: evaluate.run(m, out_dir=tmp_path, quiet=True) for m in ("baseline", "cache", "router", "router-cache")}
    assert out["baseline"]["share_small"] == 0
    assert out["router"]["share_small"] > 0.3
    assert out["cache"]["cache_read_tokens"] > 0 and out["baseline"]["cache_read_tokens"] == 0
    assert out["router-cache"]["cost_per_1k_usd"] < out["router"]["cost_per_1k_usd"] < out["baseline"]["cost_per_1k_usd"]


def test_lambda_handler():
    r = handler.handler({"question": "How many times can I withdraw per day?"}, None)
    assert r["statusCode"] == 200 and r["route"] == "simple" and r["cost_usd"] > 0
    assert handler.handler({"question": ""}, None)["statusCode"] == 400


def test_requests_match_the_converse_api_schema():
    """botocore's Stubber validates our request parameters against the real Converse API model."""
    import boto3
    from botocore.stub import Stubber

    c = boto3.client("bedrock-runtime", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="y")
    usage = {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}
    tool = {"output": {"message": {"role": "assistant", "content": [
        {"toolUse": {"toolUseId": "t1", "name": "route", "input": {"label": "complex"}}}]}},
        "stopReason": "tool_use", "usage": usage, "metrics": {"latencyMs": 1}}
    text = {"output": {"message": {"role": "assistant", "content": [{"text": "ok"}]}},
            "stopReason": "end_turn", "usage": {**usage, "cacheReadInputTokens": 100}, "metrics": {"latencyMs": 1}}
    with Stubber(c) as st:
        st.add_response("converse", tool)
        st.add_response("converse", text)
        d = router.route(c, "Why was my balance frozen?")
        a = assistant.answer(c, "Why was my balance frozen?", d.model, cache=True)
    assert d.model == config.PRIMARY_MODEL and a.usage["cacheReadInputTokens"] == 100
