import os

from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
response = client.models.generate_content(model=model, contents="Explain recursion in one sentence.")
print(response.text)
