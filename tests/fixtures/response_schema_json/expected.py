import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema={"type": "object", "properties": {"city": {"type": "string"}}},
)
print(client.models.generate_content(model=model, contents="Largest city in Japan, as JSON.", config=model_config).text)
