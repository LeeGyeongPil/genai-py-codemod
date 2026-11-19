import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
response = model.generate_content(
    "Give me JSON.",
    generation_config={"response_mime_type": "application/json", "temperature": 0.0},
)
print(response.text)
