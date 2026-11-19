from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project="demo-project", location="us-central1")

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    system_instruction="Be brief.",
    temperature=0.2,
    max_output_tokens=64,
)
response = client.models.generate_content(model=model, contents="Say hi", config=model_config)
print(response.text)
