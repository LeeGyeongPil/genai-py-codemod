import vertexai
from vertexai.generative_models import GenerativeModel

vertexai.init(project="demo-project", location="us-central1")

model = GenerativeModel("gemini-2.5-flash")
print(model.count_tokens("How many tokens?").total_tokens)
