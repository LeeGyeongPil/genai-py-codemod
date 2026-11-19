import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(tools=[types.Tool(google_search_retrieval=types.GoogleSearchRetrieval())])
print(client.models.generate_content(model=model, contents="Who won the latest chess world championship?", config=model_config).text)
