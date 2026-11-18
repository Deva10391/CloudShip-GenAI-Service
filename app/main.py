import os, time, json, hmac, logging
from collections import defaultdict, deque
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from app.cache import SemanticCache
from app.agent import run_agent

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("cloudship")

API_KEY = os.environ["API_KEY"]          # injected from Secret Manager
RATE = int(os.getenv("RATE_PER_MIN", "30"))
cache = SemanticCache(float(os.getenv("CACHE_THRESHOLD", "0.92")))
window = defaultdict(deque)
app = FastAPI()

class Query(BaseModel):
    q: str = Field(min_length=1, max_length=500)

def guard(key: str):
    if not hmac.compare_digest(key or "", API_KEY):
        raise HTTPException(401, "bad key")
    now, w = time.time(), window[key]
    while w and now - w[0] > 60:
        w.popleft()
    if len(w) >= RATE:
        raise HTTPException(429, "rate limit")
    w.append(now)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/query")
def query(body: Query, x_api_key: str = Header(None)):
    guard(x_api_key)
    t0 = time.time()
    hit = cache.get(body.q)
    if hit:
        res, src = {"answer": hit, "tokens": 0, "cost": 0.0}, "cache"
    else:
        res, src = run_agent(body.q), "agent"
        if not res["answer"].startswith("I don't know"):
            cache.put(body.q, res["answer"])  # never cache non-answers
    ms = int((time.time() - t0) * 1000)
    log.info(json.dumps({"src": src, "tokens": res["tokens"], "cost": res["cost"], "latency_ms": ms}))
    return {"answer": res["answer"], "source": src, "latency_ms": ms}
