import asyncio
import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.4})


async def main():
    response = await model.generate_content_async("Hello async world")
    print(response.text)


asyncio.run(main())
