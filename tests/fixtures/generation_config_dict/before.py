import os

import google.generativeai as genai  # Gemini SDK

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# Low temperature keeps the answers stable.
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "temperature": 0.2,  # stable
        "max_output_tokens": 64,
        "top_p": 0.9,
    },
)

response = model.generate_content("Name three colors.")
print(response.text)
