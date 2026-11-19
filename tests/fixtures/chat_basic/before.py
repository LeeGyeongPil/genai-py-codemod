import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", system_instruction="Answer in French.")
chat = model.start_chat()
print(chat.send_message("Hello!").text)
print(chat.send_message("How are you?").text)
