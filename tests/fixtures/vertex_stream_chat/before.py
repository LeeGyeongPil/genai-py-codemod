import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project="demo-project", location="europe-west4")

model = GenerativeModel("gemini-2.5-flash")
for chunk in model.generate_content("Count to three.", stream=True):
    print(chunk.text, end="")
chat = model.start_chat()
print(chat.send_message("Hello").text)
