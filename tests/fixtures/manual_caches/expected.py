import datetime
import os

import google.generativeai as genai
from google.generativeai import caching

genai.configure(api_key=os.environ["GOOGLE_API_KEY"])

cache = caching.CachedContent.create(
    model="models/gemini-2.5-flash",
    contents=["a long document"],
    ttl=datetime.timedelta(minutes=5),
)
model = genai.GenerativeModel.from_cached_content(cached_content=cache)
print(model.generate_content("Question").text)
