import faiss
import numpy as np
from typing import List, Tuple, Dict, Any

class FaissVectorIndex:
    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        # IndexFlatIP calculates inner product; with L2-normalized vectors this is cosine similarity
        self.index = faiss.IndexFlatIP(dimension)
        self.id_to_material_id: List[int] = []

    def reset(self):
        self.index.reset()
        self.id_to_material_id = []

    def add_materials(self, material_ids: List[int], vectors: np.ndarray):
        """
        Adds normalized embeddings and tracks material IDs.
        """
        if len(material_ids) == 0 or len(vectors) == 0:
            return
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)

        # Ensure vectors are normalized
        faiss.normalize_L2(vectors)
        self.index.add(vectors)
        self.id_to_material_id.extend(material_ids)

    def search(self, query_vector: np.ndarray, top_k: int = 20) -> List[Tuple[int, float]]:
        """
        Searches the index for top_k most similar vectors.
        Returns list of (material_id, similarity_score).
        """
        if self.index.ntotal == 0:
            return []

        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)
        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)

        faiss.normalize_L2(query_vector)
        k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_vector, k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx != -1 and idx < len(self.id_to_material_id):
                mat_id = self.id_to_material_id[idx]
                results.append((mat_id, float(dist)))
        return results

    @property
    def total_vectors(self) -> int:
        return self.index.ntotal
