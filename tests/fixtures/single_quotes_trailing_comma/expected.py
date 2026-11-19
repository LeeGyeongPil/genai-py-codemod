import os
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ['GOOGLE_API_KEY'])

model = 'gemini-2.5-flash'
model_config = types.GenerateContentConfig(
    temperature=0.7,
    top_k=40,
    system_instruction='Use single quotes.',
)


print(client.models.generate_content(model=model, contents='Quote me.', config=model_config).text)
