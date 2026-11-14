"""Compare the four modes and work out when the router pays for itself.

    python -m merchantbot.report            # real results
    python -m merchantbot.report --fake     # results from FAKE_BEDROCK=1 runs
"""
import argparse
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORDER = ["baseline", "cache", "router", "router-cache", "bedrock-ipr"]
LABEL = {"baseline": "All to primary", "cache": "Primary + caching", "router": "Router",
         "router-cache": "Router + caching", "bedrock-ipr": "Bedrock IPR (Nova Lite/Pro)"}


def load(fake):
    sfx = "-fake" if fake else ""
    out = {}
    for m in ORDER:
        s = ROOT / "results" / f"{m}{sfx}.summary.json"
        r = ROOT / "results" / f"{m}{sfx}.jsonl"
        if s.exists():
            out[m] = (json.loads(s.read_text()), [json.loads(l) for l in r.read_text().splitlines() if l])
    return out


def table(data):
    base = data.get("baseline", (None,))[0]
    lines = ["| | " + " | ".join(LABEL[m] for m in data) + " |", "|---|" + "---|" * len(data)]

    def row(name, fn):
        lines.append(f"| {name} | " + " | ".join(fn(s) for s, _ in data.values()) + " |")

    row("Cost per 1,000 questions", lambda s: f"${s['cost_per_1k_usd']:.3f}")
    if base:
        row("Change vs. baseline", lambda s: f"{(s['cost_per_1k_usd'] / base['cost_per_1k_usd'] - 1) * 100:+.0f}%")
    row("Golden pass rate", lambda s: f"{s['pass_rate'] * 100:.0f}% ({round(s['pass_rate'] * s['n'])}/{s['n']})")
    row("Latency p50 / p90", lambda s: f"{s['latency_p50_ms']:.0f} / {s['latency_p90_ms']:.0f} ms")
    row("Answered by the cheaper model", lambda s: f"{s['share_small'] * 100:.0f}%")
    row("Misrouted (vs. golden label)", lambda s: str(len(s["misroutes"])) if s["mode"] in ("router", "router-cache", "bedrock-ipr") else "–")
    row("Router cost share", lambda s: f"{(s['router_cost_usd'] / s['cost_usd'] * 100) if s['cost_usd'] else 0:.0f}%")
    row("Cache read tokens", lambda s: f"{s['cache_read_tokens']:,}")
    return "\n".join(lines)


def break_even(data):
    """Router pays off when share_small * (avg primary answer - avg small answer) > avg router cost."""
    if "router" not in data or "baseline" not in data:
        return "Run `baseline` and `router` first."
    base_rows = data["baseline"][1]
    rrows = data["router"][1]
    primary = sum(r["answer_cost_usd"] for r in base_rows) / len(base_rows)
    small_rows = [r for r in rrows if r["small_model"]]
    if not small_rows:
        return "The router sent nothing to the small model, so it cannot pay off on this dataset."
    small = sum(r["answer_cost_usd"] for r in small_rows) / len(small_rows)
    router = sum(r["router_cost_usd"] for r in rrows) / len(rrows)
    gap = primary - small
    if gap <= 0:
        return "The small model is not cheaper per answer here; routing only adds cost."
    be = router / gap
    share = len(small_rows) / len(rrows)
    return (f"- Average cost per answer: primary ${primary:.7f}, small ${small:.7f}\n"
            f"- Router overhead per question: ${router:.7f}\n"
            f"- Break-even: the router must send at least **{be * 100:.1f}%** of questions to the small model\n"
            f"- On this dataset it sent **{share * 100:.0f}%**, so routing "
            f"{'saves money' if share > be else 'costs more than it saves'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake", action="store_true")
    a = ap.parse_args()
    data = load(a.fake)
    if not data:
        raise SystemExit("No results yet. Run: python -m merchantbot.evaluate --mode baseline")
    if a.fake:
        print("> Offline fake results: these numbers only prove the pipeline works.\n")
    print(table(data))
    print("\n**Break-even**\n")
    print(break_even(data))
    for m, (s, _) in data.items():
        if s["misroutes"]:
            print(f"\nMisrouted by {LABEL[m]}: {', '.join(s['misroutes'])}")
    if "bedrock-ipr" in data:
        print("\nBedrock IPR chooses between Nova Lite and Nova Pro (its default Nova router), so it is a"
              " different model pair from ours: compare it with the `Router` column (no caching on either).")


if __name__ == "__main__":
    main()
