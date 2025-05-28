
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
    "faq": "context_faq.txt"
}

def detect_topic_gpt(question, openai_client=None):
    """
    Uses GPT to classify the question into a known topic category.
    Requires an OpenAI client passed in.
    """
    if openai_client is None:
        return "faq"  # fallback in test mode

    response = openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        temperature=0,
        messages=[
            {"role": "system", "content": (
                "You are a classifier for Roar in 24 Age of Sigmar event questions. "
                "Your job is to assign one topic label to each question, based on the most relevant match. "
                "Choose only one topic from this list: "
                "['scoring', 'venue', 'painting', 'schedule', 'lists', 'terrain', 'prizes', 'rules', 'faq']"
            )},
            {"role": "user", "content": f"Question: {question}\nAnswer:"}
        ]
    )

    answer = response.choices[0].message.content.strip().lower()
    return answer if answer in TOPIC_FILES else "faq"

def get_manual_context_gpt(question, openai_client, context_dir="."):
    topic = detect_topic_gpt(question, openai_client)
    file = TOPIC_FILES.get(topic)
    if not file:
        return f"Sorry, I don’t have a context file for topic: {topic}"

    path = os.path.join(context_dir, file)
    print(f"[TomBot] Topic: {topic} | File: {file} | Path: {path}")

    if not os.path.exists(path):
        return f"Error: Couldn’t find the file '{file}' at path: {path}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading context file '{file}': {str(e)}"

