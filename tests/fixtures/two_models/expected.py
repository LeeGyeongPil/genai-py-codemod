import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

fast = "gemini-2.5-flash"
fast_config = types.GenerateContentConfig(temperature=0.9)
plain = "gemini-2.5-pro"

print(client.models.generate_content(model=fast, contents="Idea for a name?", config=fast_config).text)
print(client.models.generate_content(model=plain, contents="Review this name.").text)
