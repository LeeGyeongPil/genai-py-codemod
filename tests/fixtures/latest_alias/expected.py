import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"], http_options=types.HttpOptions(api_version="v1beta"))

model = "gemini-flash-latest"
print(client.models.generate_content(model=model, contents="Hello").text)
