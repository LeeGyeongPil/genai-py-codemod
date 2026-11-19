"""Safety settings and a built-in tool, written for the old google-generativeai package."""

import os

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    safety_settings={
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    },
    tools="code_execution",
)

response = model.generate_content("What is the sum of the first 20 square numbers? Run code to check.")
print(response.text)
