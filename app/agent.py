import os, time, httpx
from app.store import retriever

OLLAMA = os.getenv("OLLAMA_URL", "http://localhost:11434")   # sidecar in the same Cloud Run instance
MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
COST_PER_SEC = float(os.getenv("COST_PER_SEC", "0.000145"))  # 5 vCPU + 10 GiB, Cloud Run request-based; verify current prices
SYSTEM = ("You are a support assistant. Answer ONLY from the context, in max 3 sentences. "
          "If the context lacks the answer, reply exactly: I don't know.")

def run_agent(q: str) -> dict:
    t0 = time.time()
    ctx = "\n\n".join(d.page_content for d in retriever().invoke(q))
    r = httpx.post(f"{OLLAMA}/api/chat", timeout=240, json={
        "model": MODEL, "stream": False, "keep_alive": -1,
        "options": {"temperature": 0.1, "num_ctx": 2048, "num_predict": 200},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Context:\n{ctx}\n\nQuestion: {q}"}],
    })
    r.raise_for_status()
    j = r.json()
    return {"answer": j["message"]["content"].strip(),
            "tokens": j.get("prompt_eval_count", 0) + j.get("eval_count", 0),
            "cost": round((time.time() - t0) * COST_PER_SEC, 6)}  # local model: cost = compute time, not tokens
