import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

result = client.models.embed_content(
    model="models/text-embedding-004",
    contents="What is the meaning of life?",
    config=types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT", title="Philosophy"),
)
print(result)
