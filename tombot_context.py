# tombot_context.py
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

with open("OTTD Roar in 24.txt", "r", encoding="utf-8") as f:
    PACK_TEXT = f.read()

CHUNKS = [PACK_TEXT[i:i+500] for i in range(0, len(PACK_TEXT), 500)]
VEC = TfidfVectorizer().fit(CHUNKS)
VEC_MATRIX = VEC.transform(CHUNKS)

def get_relevant_context(query, top_k=3):
    query_vec = VEC.transform([query])
    sims = cosine_similarity(query_vec, VEC_MATRIX).flatten()
    top_indices = sims.argsort()[-top_k:][::-1]
    return "\n---\n".join(CHUNKS[i] for i in top_indices)
