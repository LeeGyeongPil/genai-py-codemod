import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.2})
print(model.generate_content("Hi", generation_config={"max_output_tokens": 10}).text)
