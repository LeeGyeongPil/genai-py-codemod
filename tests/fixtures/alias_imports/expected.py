import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(max_output_tokens=32)
print(client.models.generate_content(model=model, contents="Say something short.", config=model_config).text)
