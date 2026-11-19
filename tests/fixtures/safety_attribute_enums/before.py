import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

safe = genai.GenerativeModel(
    "gemini-2.5-flash",
    safety_settings={genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: genai.types.HarmBlockThreshold.BLOCK_NONE},
)
print(safe.generate_content("Hello").text)
