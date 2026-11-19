"""The original script (old google-generativeai package)."""

import os

import google.generativeai as genai
from google.generativeai.types import HarmBlockThreshold, HarmCategory

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={"temperature": 0.2, "max_output_tokens": 64},
    safety_settings={HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH},
    system_instruction="Be brief.",
)

print(model.generate_content("Tell me a fun fact.").text)
