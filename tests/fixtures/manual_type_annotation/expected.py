import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


def describe(model: genai.GenerativeModel) -> str:
    return model.model_name


print(describe(genai.GenerativeModel("gemini-2.5-flash")))
