import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", system_instruction="Be brief.")
print(model.count_tokens("How long is this?").total_tokens)
