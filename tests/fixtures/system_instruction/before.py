import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    system_instruction="You are a terse assistant.",
    generation_config={"temperature": 0.0},
)
print(model.generate_content("What is 2+2?").text)
