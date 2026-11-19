import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    system_instruction="You are a terse assistant.",
    temperature=0.0,
)
print(client.models.generate_content(model=model, contents="What is 2+2?", config=model_config).text)
