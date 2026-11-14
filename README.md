# Cost-aware LLM router on Amazon Bedrock

Send easy questions to a cheap model, hard ones to a stronger model, cache the long system prompt, and
measure whether any of it actually saves money without hurting answer quality.

This is a hands-on project: you build the merchant-support chatbot for **Lapak Pesisir**, an e-commerce
marketplace for small coastal businesses in Indonesia. Merchants ask about fees, payouts, shipping, and
returns, in Indonesian or English, and every answer must come from a ~2,000-token merchant guide. The
guide and the 30 test questions ship with the repo, so you can run everything end to end yourself.

```
merchant question
      │
      ▼
 router (Nova Micro, forced tool call) ── fails? ──► primary model
      │ simple                │ complex
      ▼                       ▼
 Nova Micro + guide       Nova 2 Lite + guide        guide = cached prefix (prompt caching)
      │                       │
      └──────► answer + per-request cost (CloudWatch EMF metric)
```

What is in the repo:

| Path | What it does |
|---|---|
| `src/lapak/router.py` | Classifies a question as `simple` or `complex` with a forced tool call; falls back to the primary model on any error |
| `src/lapak/assistant.py` | Answers from the guide; puts a `cachePoint` after the static prefix |
| `src/lapak/evaluate.py` | Runs the 30-question golden dataset in one of four modes and records quality, cost, latency |
| `src/lapak/report.py` | Comparison table and break-even point for the router |
| `src/lapak/handler.py` | Lambda handler with an SSM feature flag and EMF cost metrics |
| `infra/template.yaml` | SAM template: function, least-privilege IAM, log group, flag, fallback alarm |
| `data/golden.jsonl` | 30 questions with expected facts and a `simple`/`complex` label |

## Prerequisites

- An AWS account, Region **us-east-1** (the code uses the `us.` cross-Region inference profiles).
- In the Bedrock console, **Model access** enabled for **Amazon Nova Micro** and **Amazon Nova 2 Lite**.
- Python 3.11+, AWS CLI v2, and (for the Lambda part) AWS SAM CLI.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 1. Check the pipeline offline (no AWS, no cost)

```bash
LAPAK_FAKE=1 python -m pytest -q
LAPAK_FAKE=1 PYTHONPATH=src python -m lapak.evaluate --mode baseline
LAPAK_FAKE=1 PYTHONPATH=src python -m lapak.report --fake
```

The fake client is not a model; it only proves the plumbing works. Do not publish its numbers.

## 2. Run the experiment against Bedrock (a few US cents)

```bash
export AWS_REGION=us-east-1
scripts/run-experiment.sh
```

It runs the dataset four times and prints a table like this (fill it with your own numbers):

| | All to primary | Primary + caching | Router | Router + caching |
|---|---|---|---|---|
| Cost per 1,000 questions | | | | |
| Golden pass rate | | | | |
| Latency p50 / p90 | | | | |
| Answered by small model | 0% | 0% | | |

plus the router's **break-even point**: the share of questions that must go to the small model before
the router's own cost is paid back. Per-question details are in `results/<mode>.jsonl`; look at the
`failed` and `misroutes` lists in `results/<mode>.summary.json` before trusting the averages.

Run a single mode with `PYTHONPATH=src python -m lapak.evaluate --mode router --limit 5`.

## 3. Deploy the Lambda version

```bash
scripts/deploy.sh
scripts/ask.sh "Berapa minimal penarikan saldo?"
scripts/ask.sh "A buyer orders kerupuk for Rp200,000 plus Rp20,000 shipping and pays COD. What are my fees?"
```

The response shows the route, the model that answered, and the cost of that request.

### Verify

Per-request metrics land in CloudWatch under the `LapakPesisir/Assistant` namespace (`CostUSD`,
`LatencyMs`, `CacheReadTokens`, `RouterFallback`, by `Route`). To see cost by model in Logs Insights
(log group `/aws/lambda/lapak-assistant-assistant`):

```
fields @timestamp, Route, model, CostUSD, LatencyMs, CacheReadTokens
| filter ispresent(CostUSD)
| stats count() as requests, sum(CostUSD) as cost_usd, avg(LatencyMs) as avg_ms by model
```

Switch the router off without a deploy (picked up within a minute):

```bash
aws ssm put-parameter --name /lapak-assistant/router-flags --overwrite \
  --value '{"router": false, "cache": true}'
```

## 4. Clean up

```bash
scripts/cleanup.sh
```

This deletes the function, IAM role, log group, SSM parameter, and alarm. Nothing in the stack costs
money while idle; the only charges are Bedrock tokens per request and CloudWatch logs.

## Things that tripped me up

- **`cacheWriteInputTokens` is 0 and nothing is cached.** Amazon Nova needs at least ~1K tokens before a
  `cachePoint`; a shorter prefix is silently ignored. Anything that changes per request (the question,
  retrieved chunks, today's date) must come after the checkpoint, or every request writes a new cache.
- **Cache hits vary.** With a cross-Region inference profile, a request may be served from another
  Region that has no cache yet. Judge caching by `cacheReadInputTokens` over many requests, not one call.
- **`AccessDeniedException` from Lambda.** A cross-Region profile needs `bedrock:InvokeModel` on the
  profile *and* on the foundation model in every Region it can route to (see the template).
- **The router is not free.** It adds one small-model call and some latency to every request. Use
  `report.py`'s break-even line before keeping it.

## Limits

- Grading is keyword-based: good enough to catch missing facts and wrong numbers, not tone or
  completeness. For a real launch, add human review or an LLM-as-a-judge pass on a sample.
- 30 questions is a smoke test, not a benchmark. Re-run with your own traffic before deciding.
- Prices live in `src/lapak/data/pricing.json`; check the
  [Amazon Bedrock pricing page](https://aws.amazon.com/bedrock/pricing/) before you publish numbers.

## License

MIT-0. The merchant guide and test questions are sample data for this project.
