"""A chat with streamed answers, written for the old google-generativeai package."""

import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", system_instruction="Answer like a pirate.")
chat = model.start_chat(history=[])

print(chat.send_message("Where is the treasure?").text)

# Streaming: the answer arrives in chunks.
for chunk in model.generate_content("Sing one line about the sea.", stream=True):
    print(chunk.text, end="")
print()
