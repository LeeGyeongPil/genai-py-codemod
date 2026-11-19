import os

import google.generativeai as gg
from google.generativeai import GenerativeModel as GM

gg.configure(api_key=os.environ["GOOGLE_API_KEY"])

model = GM("gemini-2.5-flash", generation_config={"max_output_tokens": 32})
print(model.generate_content("Say something short.").text)
