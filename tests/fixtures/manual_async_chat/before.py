import asyncio
import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat()


async def main():
    print((await chat.send_message_async("Hi")).text)


asyncio.run(main())
