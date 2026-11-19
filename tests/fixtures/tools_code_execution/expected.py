import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(tools=[types.Tool(code_execution=types.ToolCodeExecution())])
print(client.models.generate_content(model=model, contents="What is the sum of the first 50 primes?", config=model_config).text)
