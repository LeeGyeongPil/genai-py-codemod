import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

# A low temperature keeps the summaries stable between runs.
model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    temperature=0.2,  # stable output
    max_output_tokens=128,
    system_instruction="Summarize in one sentence.",
)

response = client.models.generate_content(model=model, contents="Cats sleep for most of the day and hunt at dusk.", config=model_config)
print(response.text)
