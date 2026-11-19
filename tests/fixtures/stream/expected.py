import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(temperature=0.5)

for chunk in client.models.generate_content_stream(model=model, contents="Write a haiku.", config=model_config):
    print(chunk.text, end="")
print()
