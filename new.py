# from sentence_transformers import SentenceTransformer
# model = SentenceTransformer("all-MiniLM-L6-v2")
# print(model.encode("hello world"))
#current time

from datetime import datetime,timezone
print("Current time:", datetime.utcnow)
print("current date:", datetime.now(timezone.utc))
print("current time:", datetime.now())