import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    safety_settings={"harassment": "block_none", "hate": "block_only_high"},
)
print(model.generate_content("Hello").text)
