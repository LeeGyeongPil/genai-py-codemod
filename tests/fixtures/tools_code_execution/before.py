import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", tools="code_execution")
print(model.generate_content("What is the sum of the first 50 primes?").text)
