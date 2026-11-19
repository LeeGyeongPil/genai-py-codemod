import vertexai
from vertexai.generative_models import GenerativeModel, HarmBlockThreshold, HarmCategory, SafetySetting

vertexai.init(project="demo-project", location="us-central1")

model = GenerativeModel(
    "gemini-2.5-flash",
    safety_settings=[
        SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_ONLY_HIGH),
    ],
)
print(model.generate_content("Hello").text)
