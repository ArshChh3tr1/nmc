import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL_NAME

class TextEmbedder:
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        # SentenceTransformer handles local caching automatically
        self.model = SentenceTransformer(model_name)

    def embed_texts(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        Generates L2-normalized embeddings for given text(s).
        Returns numpy array of shape (N, 384) with dtype float32.
        """
        if isinstance(texts, str):
            texts = [texts]
        if not texts:
            return np.empty((0, 384), dtype=np.float32)

        # encode and normalize to unit length for cosine similarity
        embeddings = self.model.encode(
            texts,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        return embeddings.astype(np.float32)

_embedder_instance = None

def get_embedder() -> TextEmbedder:
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = TextEmbedder()
    return _embedder_instance

def compute_embedding(text: str) -> np.ndarray:
    embedder = get_embedder()
    vecs = embedder.embed_texts([text])
    return vecs[0]
