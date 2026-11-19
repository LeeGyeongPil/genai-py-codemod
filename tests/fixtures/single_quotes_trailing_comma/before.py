import os
import google.generativeai as genai

genai.configure(api_key=os.environ['GOOGLE_API_KEY'])

model = genai.GenerativeModel(
    'gemini-2.5-flash',
    generation_config={'temperature': 0.7, 'top_k': 40,},
    system_instruction='Use single quotes.',
)


print(model.generate_content('Quote me.').text)
