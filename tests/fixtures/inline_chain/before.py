import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

print(genai.GenerativeModel("gemini-2.5-flash").generate_content("One-liner about the sea.").text)
print(genai.GenerativeModel("gemini-2.5-flash", system_instruction="Be brief.").generate_content("Hi").text)
