import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

print(client.models.generate_content(model="gemini-2.5-flash", contents="One-liner about the sea.").text)
print(client.models.generate_content(model="gemini-2.5-flash", contents="Hi", config=types.GenerateContentConfig(system_instruction="Be brief.")).text)
