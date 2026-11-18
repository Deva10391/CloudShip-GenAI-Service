import os, sys, tempfile
from llama_index.core import SimpleDirectoryReader
from llama_index.core.node_parser import SentenceSplitter
from langchain_qdrant import QdrantVectorStore
from app.store import embeddings, URL, KEY, COL

def ingest_dir(d: str):
    docs = SimpleDirectoryReader(d).load_data()
    nodes = SentenceSplitter(chunk_size=512, chunk_overlap=50).get_nodes_from_documents(docs)
    QdrantVectorStore.from_texts([n.get_content() for n in nodes], embeddings(),
                                 url=URL, api_key=KEY, collection_name=COL)

if __name__ == "__main__":
    ingest_dir(sys.argv[1])        # local:  python -m app.ingest ./kb

