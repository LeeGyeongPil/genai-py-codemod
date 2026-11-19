import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"], transport="rest")

model = genai.GenerativeModel("gemini-2.5-flash")
print(model.generate_content("Hi").text)
