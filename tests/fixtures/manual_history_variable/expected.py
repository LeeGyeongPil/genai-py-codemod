import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

saved = [{"role": "user", "parts": [os.environ.get("FIRST", "hi")]}]
model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat(history=saved)
print(chat.send_message("Hello").text)
