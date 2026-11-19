import os

from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
model = MODEL_NAME
print(client.models.generate_content(model=model, contents="Hello").text)
