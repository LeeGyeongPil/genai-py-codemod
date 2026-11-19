import os

import google.generativeai as genai

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config=genai.types.GenerationConfig(temperature=0.1, top_k=20, candidate_count=1),
)
print(model.generate_content("Hi").text)
