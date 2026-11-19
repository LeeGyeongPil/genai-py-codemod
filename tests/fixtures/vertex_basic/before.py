import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

vertexai.init(project="demo-project", location="us-central1")

model = GenerativeModel(
    "gemini-2.5-flash",
    system_instruction="Be brief.",
    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=64),
)
response = model.generate_content("Say hi")
print(response.text)
