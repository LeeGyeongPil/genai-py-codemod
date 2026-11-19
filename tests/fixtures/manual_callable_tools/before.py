import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])


def multiply(a: float, b: float) -> float:
    """Return a * b."""
    return a * b


model = genai.GenerativeModel("gemini-2.5-flash", tools=[multiply])
print(model.generate_content("What is 3 times 4?").text)
