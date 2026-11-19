import os

from google import genai

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

model = "gemini-2.5-flash"
chat = client.chats.create(
    model=model,
    history=[
        {"role": "user", "parts": [{"text": "Hi there"}]},
        {"role": "model", "parts": [{"text": "Hello! How can I help?"}]},
    ],
)
for part in chat.send_message_stream("Tell me a story."):
    print(part.text, end="")
print()
