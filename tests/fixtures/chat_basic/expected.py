import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(system_instruction="Answer in French.")
chat = client.chats.create(model=model, config=model_config)
print(chat.send_message("Hello!").text)
print(chat.send_message("How are you?").text)
