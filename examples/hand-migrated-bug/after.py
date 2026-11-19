"""A hand migration that looks right but silently drops settings."""

import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# The temperature and the safety settings were forgotten while moving the call.
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Tell me a fun fact.",
    config=types.GenerateContentConfig(
        max_output_tokens=64,
        system_instruction="Be brief.",
    ),
)
print(response.text)
