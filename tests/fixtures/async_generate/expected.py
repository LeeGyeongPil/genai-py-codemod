import asyncio
import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(temperature=0.4)


async def main():
    response = await client.aio.models.generate_content(model=model, contents="Hello async world", config=model_config)
    print(response.text)


asyncio.run(main())
