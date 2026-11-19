import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

# A low temperature keeps the summaries stable between runs.
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "temperature": 0.2,  # stable output
        "max_output_tokens": 128,
    },
    system_instruction="Summarize in one sentence.",
)

response = model.generate_content("Cats sleep for most of the day and hunt at dusk.")
print(response.text)
