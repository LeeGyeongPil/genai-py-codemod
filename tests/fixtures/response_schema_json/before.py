import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "response_mime_type": "application/json",
        "response_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
    },
)
print(model.generate_content("Largest city in Japan, as JSON.").text)
