import os

from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
usage = client.models.count_tokens(model=model, contents="How many tokens is this sentence?")
print(usage.total_tokens)
