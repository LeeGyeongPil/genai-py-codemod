import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

OPTIONS = {"stream": False}
model = genai.GenerativeModel("gemini-2.5-flash")
print(model.generate_content("Hi", **OPTIONS).text)
