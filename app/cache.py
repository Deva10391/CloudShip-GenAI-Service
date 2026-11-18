import os, uuid
from qdrant_client import QdrantClient

COL = "semantic_cache"

class SemanticCache:
    def __init__(self, threshold: float):
        self.t = threshold  # tune on your 100+ queries, never guess
        self.c = QdrantClient(url=os.environ["QDRANT_URL"], api_key=os.getenv("QDRANT_KEY"))

    def get(self, q: str):
        try:
            r = self.c.query(COL, query_text=q, limit=1)
        except Exception:
            return None  # empty collection on first run
        if r and r[0].score >= self.t:
            return r[0].metadata["answer"]
        return None

    def put(self, q: str, a: str):
        self.c.add(COL, documents=[q], metadata=[{"answer": a}], ids=[str(uuid.uuid4())])
