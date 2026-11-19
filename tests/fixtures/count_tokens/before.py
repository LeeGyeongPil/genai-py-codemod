import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
usage = model.count_tokens("How many tokens is this sentence?")
print(usage.total_tokens)
