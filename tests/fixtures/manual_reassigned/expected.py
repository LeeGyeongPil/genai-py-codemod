import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
if os.environ.get("USE_PRO"):
    model = genai.GenerativeModel("gemini-2.5-pro")
print(model.generate_content("Hi").text)
