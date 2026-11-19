import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.5})

for chunk in model.generate_content("Write a haiku.", stream=True):
    print(chunk.text, end="")
print()
