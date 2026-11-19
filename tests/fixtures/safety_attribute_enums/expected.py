import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

safe = "gemini-2.5-flash"
safe_config = types.GenerateContentConfig(
    safety_settings=[types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)],
)
print(client.models.generate_content(model=safe, contents="Hello", config=safe_config).text)
