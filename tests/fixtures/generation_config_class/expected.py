import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    temperature=0.1,
    top_k=20,
    candidate_count=1,
)
print(client.models.generate_content(model=model, contents="Hi", config=model_config).text)
