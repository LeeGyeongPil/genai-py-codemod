import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config=genai.GenerationConfig(
        temperature=0.3,
        top_p=0.8,  # nucleus sampling
    ),
)
response = model.generate_content(
    "Write a limerick.",
)
print(response.text)
