# CloudShip GenAI Service

> **Runs fully local; no API keys, no paid services. Load test: 442 requests, 0 failures, p95 46 ms, 99.9% served from cache (5 users, 3 min, 120 paraphrased queries, warm cache).**

A FastAPI service that answers from your documents with a self-hosted `qwen2.5:3b` (Ollama), vectors in a local Qdrant. No LLM API key, no per-token bill, no cloud account.

**Requirements**
- Python 3.11+, Docker.
- Ollama with `qwen2.5:3b` pulled (on the host, or as the compose container).
- A knowledge base to ingest (text, PDF or docx files in a local folder; `kb/` ships with one sample).
- 100+ test queries including paraphrases (`loadtest/queries.txt` holds 120, built from 24 phrasings x 5 prefixes).

**Open-source utilities**
- Ollama `qwen2.5:3b` (LLM), Qdrant + FastEmbed `bge-small` (vectors, cache), LangChain (retriever), LlamaIndex (load and chunk).
- FastAPI + Pydantic (API), Locust (load test), Docker.

**Working amongst components**
```
POST /query -> key + rate limit -> semantic cache -> hit: answer | miss: Qdrant top 4 -> qwen2.5:3b -> answer + cache
```
1. `docker compose` runs `qdrant` and `app` (FastAPI), plus an `ollama` container unless you use your host Ollama.
2. `/query` checks the API key and a per-minute rate limit.
3. A similar earlier question (score >= `CACHE_THRESHOLD`) returns the cached answer with 0 tokens.
4. Otherwise the top 4 chunks go to the model, which must answer only from them or say "I don't know".
5. Every request logs source, tokens, cost and latency as one JSON line.

**Details to know**
- No keys needed: the API key is a plain env var (`dev-key` in `docker-compose.yml`); change it for anything shared.
- `cost` in the log = seconds x `COST_PER_SEC`. The default is a cloud estimate; set `COST_PER_SEC=0` for local use.
- "I don't know" answers are never cached.
- Cache threshold defaults to 0.92 and must be tuned on your own queries, not guessed.
- CPU only: the first start downloads the embedding model and the first request loads the LLM, so wait for readiness before load testing.
- The load-test queries all cover one topic (the sample `kb/password.md`), so the cache hit rate is high by design; it says nothing about a mixed workload.

**Simplified working:** ingest -> query -> cache or (retrieve + model) -> log latency.

## Run locally
```bash
docker compose up -d --build                                  # qdrant + app (+ ollama container)
docker compose exec ollama ollama pull qwen2.5:3b             # skip if you use host Ollama
until curl -sf localhost:6333/healthz >/dev/null; do sleep 2; done
until curl -sf localhost:8080/health >/dev/null; do sleep 2; done
docker compose cp kb/. app:/srv/kb
docker compose exec app python -m app.ingest ./kb             # runs inside the container, no host Python needed
curl -X POST localhost:8080/query -H "x-api-key: dev-key" -H "Content-Type: application/json" -d '{"q":"How do I reset my password?"}'
```
Do not type `<placeholders>`: the shell reads `<` as redirection.

### Use the Ollama you already have (skip the container)
```bash
docker compose stop ollama
cat > docker-compose.override.yml <<'E'
services:
  app:
    environment:
      OLLAMA_URL: http://host.docker.internal:11434
    extra_hosts:
      - "host.docker.internal:host-gateway"
E
docker compose up -d --no-deps qdrant app
```
If the host Ollama listens only on `127.0.0.1`, start it with `OLLAMA_HOST=0.0.0.0 ollama serve`.

## Load test
Raise the rate limit for the test (`RATE_PER_MIN: "100000"` under `app.environment` in the override file), then:
```bash
T=$(date -u +%Y-%m-%dT%H:%M:%S)
mkdir -p results
API_KEY=dev-key locust -f loadtest/locustfile.py --host http://localhost:8080 --headless -u 5 -r 1 -t 3m --csv=results/results
docker compose logs app --no-log-prefix --since "$T" | grep '^{"src"' > q.log
python - <<'E'
import json,csv
r=[json.loads(l) for l in open("q.log")]
L=sorted(x["latency_ms"] for x in r)
f=[row for row in csv.DictReader(open("results/results_stats.csv")) if row["Name"]=="Aggregated"][0]
print("failures",f["Failure Count"],"of",f["Request Count"],"| p95 ms",L[int(.95*len(L))-1],"| cache %",round(100*sum(x["src"]=="cache" for x in r)/len(r),1))
E
```
Quote a result only if `failures` is 0.

## Results

Measured with the Load test block below: local CPU, host Ollama `qwen2.5:3b`, one-document knowledge base, 5 users for 3 minutes.

| Metric | Value |
|---|---|
| Requests / failures | 442 / 0 |
| p95 latency (from app log) | 46 ms |
| Repeat queries served from cache | 99.9% |
| Queries in the test | 120 distinct paraphrases of one topic |

Read these as cache-path numbers: the cache was already warm from earlier runs and all queries share one topic, so almost nothing reached the model. A fresh (uncached) answer takes seconds on CPU and was not part of this p95. The app log held 888 lines for 442 requests (each request logged twice), which does not change the percentages.

## API
| Route | Does |
|---|---|
| `POST /query` | header `x-api-key`, body `{"q": "..."}` -> answer, source (`cache` or `agent`), latency_ms |
| `GET /health` | liveness (does not check Qdrant or Ollama) |

Settings (env): `API_KEY`, `QDRANT_URL`, `QDRANT_KEY`, `OLLAMA_URL`, `OLLAMA_MODEL`, `CACHE_THRESHOLD`, `RATE_PER_MIN`, `COST_PER_SEC`.

## Troubleshooting
| Error | Cause | Fix |
|---|---|---|
| `port is already allocated` on 6333 | Another project's Qdrant holds the port | `docker stop $(docker ps -q --filter publish=6333)` |
| `address already in use` on 11434 | Ollama is already running | Use it: see "Use the Ollama you already have" |
| Ingest on the host hangs or is very slow | Heavy Python imports on the host | Ingest inside the container (see Run locally) |
| `Connection refused` from ingest or Locust | Qdrant or app not ready yet | Wait for the two `until curl` lines to finish |
| `Internal Server Error` on `/query` | Nothing ingested, so collection `kb` is missing | Run the ingest line |
| `KeyError: 'QDRANT_URL'` or `'API_KEY'` | Env var not set | Set it (compose sets it for the containers) |
| `401 bad key` | `x-api-key` header missing or wrong | Send the `API_KEY` value |
| `429 rate limit` | More than `RATE_PER_MIN` (default 30) per minute | Wait, or raise `RATE_PER_MIN` |
| Model not found or first request very slow | Model not pulled yet, or still loading | Pull the model, then retry |

## Safety
API key and rate limit on `/query`, query length capped at 500 characters, no cloud credentials anywhere in the project.

## When NOT to use an agent
Fixed-answer lookups, hard latency budgets, or flows a plain search or SQL query already solves.

## Limits
- The rate limiter keeps counts in memory, so it resets on restart.
- `qwen2.5:3b` is under the Qwen Research License (non-commercial); for commercial use switch `OLLAMA_MODEL` and the pull command to an Apache 2.0 model such as `qwen2.5:1.5b` or `qwen2.5:7b`.
- Small model: answers can be wrong or too cautious ("I don't know"); check them on your own queries.
- Load-test numbers are local CPU numbers, not cloud numbers, and measure the cache path (see Results).

## Files
`app/main.py` API, key, rate limit · `app/agent.py` retrieve and ask the model · `app/store.py` retriever · `app/cache.py` semantic cache · `app/ingest.py` local folder to Qdrant · `ollama/Dockerfile` Ollama image · `docker-compose.yml` local stack · `loadtest/locustfile.py` and `loadtest/queries.txt` load test