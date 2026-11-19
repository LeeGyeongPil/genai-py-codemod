import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")
sample = genai.upload_file("notes.txt")
print(model.generate_content([sample, "Summarize the file."]).text)
