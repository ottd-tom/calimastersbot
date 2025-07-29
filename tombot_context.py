
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Load the event pack text
with open("OTTD Roar in 24.txt", "r", encoding="utf-8") as f:
    PACK_TEXT = f.read()

# Chunk the text by logical paragraph units
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

# Create the chunks
CHUNKS = split_into_chunks(PACK_TEXT)
VEC = TfidfVectorizer().fit(CHUNKS)
VEC_MATRIX = VEC.transform(CHUNKS)

# Tag chunks for fallback logic
TAGGED_CHUNKS = []
for chunk in CHUNKS:
    tags = []
    lower = chunk.lower()
    if any(k in lower for k in ["score", "scoring", "tiebreaker", "bcp", "battle point"]):
        tags.append("scoring")
    if any(k in lower for k in ["venue", "location", "lake forest", "community center", "where"]):
        tags.append("venue")
    if any(k in lower for k in ["paint", "painting", "model", "appearance"]):
        tags.append("painting")
    if any(k in lower for k in ["round", "schedule", "start", "registration", "time", "saturday", "sunday"]):
        tags.append("schedule")
    if any(k in lower for k in ["terrain", "table", "layout", "map", "deployment"]):
        tags.append("terrain")
    if any(k in lower for k in ["list", "army list", "submit", "submission", "deadline", "lists"]):
        tags.append("lists")
    if any(k in lower for k in ["food", "lunch", "snack", "dinner", "meal", "break"]):
        tags.append("food")
    if any(k in lower for k in ["faq", "question", "ruling", "clarification", "q:"]):
        tags.append("faq")
    if any(k in lower for k in ["prize", "award", "trophy", "raffle"]):
        tags.append("prizes")
    TAGGED_CHUNKS.append({"text": chunk, "tags": tags})

# Keyword definitions for tag matching
TAG_KEYWORDS = {
    "scoring": ["score", "scoring", "points", "tiebreaker", "bcp"],
    "venue": ["location", "venue", "where"],
    "painting": ["paint", "painting", "model", "appearance"],
    "schedule": ["round", "schedule", "start", "registration", "time", "saturday", "sunday"],
    "terrain": ["terrain", "table", "layout", "map", "deployment"],
    "lists": ["list", "army list", "submit", "submission", "deadline"],
    "food": ["food", "lunch", "snack", "dinner", "meal", "break"],
    "faq": ["faq", "question", "ruling", "clarification", "q:"],
    "prizes": ["prize", "award", "trophy", "raffle"]
}

# Main retriever with fallback injection
def get_relevant_context(query, top_k=3):
    query_vec = VEC.transform([query])
    sims = cosine_similarity(query_vec, VEC_MATRIX).flatten()
    top_indices = sims.argsort()[-top_k:][::-1]
    top_chunks = [CHUNKS[i] for i in top_indices]

    # Match tags based on query keywords
    lower_query = query.lower()
    matched_tags = [tag for tag, keywords in TAG_KEYWORDS.items() if any(k in lower_query for k in keywords)]

    # Inject matching tagged chunks
    injected_chunks = []
    for chunk in TAGGED_CHUNKS:
        if any(tag in chunk["tags"] for tag in matched_tags):
            if chunk["text"] not in top_chunks and chunk["text"] not in injected_chunks:
                injected_chunks.append(chunk["text"])

    combined_chunks = injected_chunks + top_chunks
    return "\n---\n".join(combined_chunks[:top_k + len(injected_chunks)])
