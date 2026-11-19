from google import genai
from google.genai import types

client = genai.Client(vertexai=True, project="demo-project", location="us-central1")

model = "gemini-2.5-flash"
model_config = types.GenerateContentConfig(
    safety_settings=[
        types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH),
    ],
)
print(client.models.generate_content(model=model, contents="Hello", config=model_config).text)
