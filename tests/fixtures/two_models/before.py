import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

fast = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.9})
plain = genai.GenerativeModel("gemini-2.5-pro")

print(fast.generate_content("Idea for a name?").text)
print(plain.generate_content("Review this name.").text)
