"""A script written for the Vertex AI SDK generative module (vertexai.generative_models)."""

import vertexai
from vertexai.generative_models import GenerationConfig, GenerativeModel

vertexai.init(project="my-project", location="us-central1")

model = GenerativeModel(
    "gemini-2.5-flash",
    system_instruction="Be brief.",
    generation_config=GenerationConfig(temperature=0.2, max_output_tokens=64),
)

response = model.generate_content("Say hello in three languages.")
print(response.text)
