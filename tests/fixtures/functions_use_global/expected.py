import os

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

MODEL = "gemini-2.5-flash"
MODEL_CONFIG = types.GenerateContentConfig(temperature=0.3)


def summarize(text):
    return client.models.generate_content(model=MODEL, contents=f"Summarize: {text}", config=MODEL_CONFIG).text


def main():
    print(summarize("Cats sleep a lot."))
    print(summarize("Dogs bark."))


if __name__ == "__main__":
    main()
