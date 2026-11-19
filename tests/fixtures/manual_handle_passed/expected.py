import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel("gemini-2.5-flash")


def ask(m, question):
    return m.generate_content(question).text


print(ask(model, "Hi"))
