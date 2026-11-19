from google import genai

client = genai.Client(vertexai=True, project="demo-project", location="europe-west4")

model = "gemini-2.5-flash"
for chunk in client.models.generate_content_stream(model=model, contents="Count to three."):
    print(chunk.text, end="")
chat = client.chats.create(model=model)
print(chat.send_message("Hello").text)
