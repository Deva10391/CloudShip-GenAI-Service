import os, random
from locust import HttpUser, task, between

QS = [l.strip() for l in open(os.path.join(os.path.dirname(__file__), "queries.txt")) if l.strip()]

class U(HttpUser):
    wait_time = between(1, 3)
    @task
    def ask(self):
        self.client.post("/query", json={"q": random.choice(QS)},
                         headers={"x-api-key": os.environ["API_KEY"]})
