import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
chat = model.start_chat(
    history=[
        {"role": "user", "parts": ["Hi there"]},
        {"role": "model", "parts": ["Hello! How can I help?"]},
    ],
)
for part in chat.send_message("Tell me a story.", stream=True):
    print(part.text, end="")
print()
