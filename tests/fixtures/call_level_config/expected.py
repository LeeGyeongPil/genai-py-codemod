import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
response = client.models.generate_content(
    model=model,
    contents="Give me JSON.",
    config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.0),
)
print(response.text)
