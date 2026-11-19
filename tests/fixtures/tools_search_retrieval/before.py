import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash", tools=["google_search_retrieval"])
print(model.generate_content("Who won the latest chess world championship?").text)
