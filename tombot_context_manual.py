
import os

# Map topics to manual context files
TOPIC_FILES = {
    "scoring": "context_scoring.txt",
    "venue": "context_location.txt",
    "painting": "context_painting.txt",
    "schedule": "context_schedule.txt",
    "lists": "context_lists.txt",
    "terrain": "context_terrain.txt",
    "prizes": "context_prizes.txt",
    "rules": "context_rules.txt",
    "faq": "context_faq.txt",
    "pairings": "context_pairings.txt",
    "players": "context_players.txt",
    "missions": "context_missions.txt",
    "food":    "context_food.txt",
    "other": "context_other.txt"
}
def detect_topic_gpt(question, openai_client=None):
    """
    Uses GPT to classify the question into a known topic category.
    Falls back to 'faq' if no client provided.
    """
    if openai_client is None:
        return "faq"

    # Call the module-level ChatCompletion API
    response = openai_client.ChatCompletion.create(
        model="gpt-4",
        temperature=0,
        max_tokens=10,
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a classifier for Summer Strike Age of Sigmar event questions. "
                    "Your job is to assign exactly one topic label to each question, choosing from:\n"
                    "['scoring', 'venue', 'painting', 'schedule', 'lists', "
                    "'terrain', 'prizes', 'rules', 'faq', 'pairings', 'players', 'food'].\n\n"
                    "Rules:\n"
                    "- Questions about who is likely to win or how strong a player is → 'players'.\n"
                    "- Questions about missions, plans or what we're playing → 'missions'.\n"
                    "- Questions about food, the bar, alcohol, lunch, or what is available to eat or drink → 'food'.\n"
                    "- Questions about army list submission, deadlines, or when to turn in your roster → 'lists'.\n\n"
                    "Examples:\n"
                    "Q: When is list submission?           → lists\n"
                    "Q: When are lists due?                → lists\n"
                    "Q: What time do rounds start?         → schedule\n"
                    "Q: Where is the event held?           → venue\n"
                    "Q: Who is the favorite to win today?  → players\n"
                    "Q: How do tiebreakers work?          → scoring\n\n"
                    "Now classify this question (one label only):"
                )
            },
            {
                "role": "user",
                "content": f"Question: {question}\nAnswer:"
            }
        ]

    )

    answer = response.choices[0].message.content.strip().lower()
    topic  = answer.rstrip("s") if answer.rstrip("s") in TOPIC_FILES else answer
    if topic not in TOPIC_FILES:
        topic = "other"
    return topic


def get_manual_context_gpt(question, openai_client, context_dir="."):
    topic = detect_topic_gpt(question, openai_client)
    file = TOPIC_FILES.get(topic)
    if not file:
        return topic, f"Sorry, I don’t have a context file for topic: {topic}"

    path = os.path.join(context_dir, file)
    print(f"[TomBot] Topic: {topic} | File: {file} | Path: {path}")

    if not os.path.exists(path):
        return topic, f"Error: Couldn’t find the file '{file}' at path: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            return topic, f.read()
    except Exception as e:
        return topic, f"Error reading context file '{file}': {str(e)}"

