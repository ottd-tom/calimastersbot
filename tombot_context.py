import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

with open("OTTD Roar in 24.txt", "r", encoding="utf-8") as f:
    PACK_TEXT = f.read()

def split_into_chunks(text, max_chunk_length=500):
    paragraphs = re.split(r"\n{2,}", text)
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) < max_chunk_length:
            current_chunk += para + "\n\n"
        else:
            chunks.append(current_chunk.strip())
            current_chunk = para + "\n\n"
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

CHUNKS = split_into_chunks(PACK_TEXT)
VEC = TfidfVectorizer().fit(CHUNKS)
VEC_MATRIX = VEC.transform(CHUNKS)

FALLBACK_KEYWORDS = {
    "scoring": ["score", "scoring", "points", "tiebreaker", "BCP"],
    "venue": ["location", "venue", "where"],
    "paint": ["paint", "painting", "model"],
    "schedule": ["round", "start", "time", "registration", "timing"]
}

def get_relevant_context(query, top_k=3):
    query_vec = VEC.transform([query])
    sims = cosine_similarity(query_vec, VEC_MATRIX).flatten()
    top_indices = sims.argsort()[-top_k:][::-1]
    results = [CHUNKS[i] for i in top_indices]

    # Add scoring chunk if relevant terms detected
    lower_query = query.lower()
    for tag, keywords in FALLBACK_KEYWORDS.items():
        if any(k in lower_query for k in keywords):
            for chunk in CHUNKS:
                if any(k in chunk.lower() for k in keywords):
                    if chunk not in results:
                        results.insert(0, chunk)  # High priority
                    break

    return "\n---\n".join(results)
