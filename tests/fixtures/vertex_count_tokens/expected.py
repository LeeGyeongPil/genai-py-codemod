from google import genai

client = genai.Client(vertexai=True, project="demo-project", location="us-central1")

model = "gemini-2.5-flash"
print(client.models.count_tokens(model=model, contents="How many tokens?").total_tokens)
