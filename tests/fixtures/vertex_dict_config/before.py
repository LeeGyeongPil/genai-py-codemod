import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project="demo-project", location="us-central1")

model = GenerativeModel("gemini-2.5-flash", generation_config={"temperature": 0.4, "top_k": 10})
print(model.generate_content("Hello").text)
