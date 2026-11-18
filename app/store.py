import os
from functools import lru_cache
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_qdrant import QdrantVectorStore

URL, KEY, COL = os.environ["QDRANT_URL"], os.getenv("QDRANT_KEY"), "kb"

@lru_cache
def embeddings():
    return FastEmbedEmbeddings()  # CPU, local, bge-small: no API key, no cost

@lru_cache
def retriever():
    # lazy: collection exists only after first ingest. Swappable: any LangChain retriever fits.
    s = QdrantVectorStore.from_existing_collection(
        embedding=embeddings(), url=URL, api_key=KEY, collection_name=COL)
    return s.as_retriever(search_kwargs={"k": 4})
