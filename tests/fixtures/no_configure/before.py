import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.5-flash")
print(model.generate_content("Hello from the environment.").text)
