import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

MODEL = genai.GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.3})


def summarize(text):
    return MODEL.generate_content(f"Summarize: {text}").text


def main():
    print(summarize("Cats sleep a lot."))
    print(summarize("Dogs bark."))


if __name__ == "__main__":
    main()
