import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    temperature=0.3,
    top_p=0.8,  # nucleus sampling
)
response = client.models.generate_content(
    model=model,
    contents="Write a limerick.",
    config=model_config,
)
print(response.text)
