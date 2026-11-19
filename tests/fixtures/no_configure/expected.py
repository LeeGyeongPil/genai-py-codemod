from google import genai

client = genai.Client()

model = "gemini-2.5-flash"
print(client.models.generate_content(model=model, contents="Hello from the environment.").text)
