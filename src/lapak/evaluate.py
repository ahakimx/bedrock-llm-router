"""Run the golden dataset through one mode and record answers, quality, cost, and latency.

    python -m lapak.evaluate --mode baseline
    python -m lapak.evaluate --mode router-cache
"""
import argparse
import json
import pathlib
import statistics
import sys
import time

from . import bedrock, config
from .grading import grade
from .service import MODES, ask

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_golden(limit=None):
    rows = [json.loads(l) for l in (ROOT / "data" / "golden.jsonl").read_text().splitlines() if l.strip()]
    return rows[:limit] if limit else rows


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def summarize(mode, rows):
    n = len(rows)
    routed = [r for r in rows if r["route_reason"] == "classified"]
    misroutes = [r["id"] for r in routed if r["route"] != r["label"]]
    return {
        "mode": mode,
        "fake": config.FAKE,
        "n": n,
        "pass_rate": sum(r["pass"] for r in rows) / n,
        "cost_usd": sum(r["cost_usd"] for r in rows),
        "cost_per_1k_usd": sum(r["cost_usd"] for r in rows) / n * 1000,
        "router_cost_usd": sum(r["router_cost_usd"] for r in rows),
        "latency_p50_ms": statistics.median(r["latency_ms"] for r in rows),
        "latency_p90_ms": pct([r["latency_ms"] for r in rows], 0.9),
        "share_small": sum(r["small_model"] for r in rows) / n,
        "router_errors": sum(r["route_reason"] == "router-error" for r in rows),
        "misroutes": misroutes,
        "failed": [r["id"] for r in rows if not r["pass"]],
        "cache_read_tokens": sum(r["usage"].get("cacheReadInputTokens", 0) for r in rows),
        "cache_write_tokens": sum(r["usage"].get("cacheWriteInputTokens", 0) for r in rows),
        "input_tokens": sum(r["usage"].get("inputTokens", 0) for r in rows),
        "output_tokens": sum(r["usage"].get("outputTokens", 0) for r in rows),
        "models": {"primary": config.PRIMARY_MODEL, "small": config.SMALL_MODEL, "router": config.ROUTER_MODEL},
        "region": config.REGION,
        "ran_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run(mode, limit=None, out_dir=ROOT / "results", quiet=False):
    use_router, use_cache = MODES[mode]
    brt = bedrock.client()
    rows = []
    for g in load_golden(limit):
        r = ask(brt, g["question"], use_router, use_cache)
        r.update(id=g["id"], label=g["label"], question=g["question"], **{"pass": grade(r["answer"], g["expect"])})
        rows.append(r)
        if not quiet:
            mark = "PASS" if r["pass"] else "FAIL"
            print(f"{g['id']} {mark} {r['route']:7} {r['model'].split('.')[-1]:16} "
                  f"${r['cost_usd']:.6f} {r['latency_ms']:5} ms", file=sys.stderr)
    out_dir.mkdir(exist_ok=True)
    suffix = "-fake" if config.FAKE else ""
    (out_dir / f"{mode}{suffix}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    s = summarize(mode, rows)
    (out_dir / f"{mode}{suffix}.summary.json").write_text(json.dumps(s, indent=2))
    return s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=list(MODES), required=True)
    ap.add_argument("--limit", type=int, help="only the first N questions (smoke test)")
    a = ap.parse_args()
    s = run(a.mode, a.limit)
    print(json.dumps({k: s[k] for k in ("mode", "n", "pass_rate", "cost_per_1k_usd", "latency_p50_ms",
                                         "share_small", "misroutes", "failed")}, indent=2))


if __name__ == "__main__":
    main()
