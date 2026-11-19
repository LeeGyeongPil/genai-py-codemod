import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


class Assistant:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    def ask(self, question):
        return self.model.generate_content(question).text


print(Assistant().ask("Hi"))
