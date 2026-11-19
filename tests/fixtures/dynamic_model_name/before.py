import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")
model = genai.GenerativeModel(MODEL_NAME)
print(model.generate_content("Hello").text)
