import os

from google import genai  # Gemini SDK
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# Low temperature keeps the answers stable.
model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    temperature=0.2,  # stable
    max_output_tokens=64,
    top_p=0.9,
)

response = client.models.generate_content(model=model, contents="Name three colors.", config=model_config)
print(response.text)
