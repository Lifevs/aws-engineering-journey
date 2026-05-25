import time
from locust import HttpUser, task, between

class LooseCouplingLoadTest(HttpUser):
    # Simulate a user waiting between 1 to 2 seconds between requests
    wait_time = between(1, 2)

    @task
    def test_loose_coupling_endpoint(self):
        """
        Sends a request to the loosely coupled API endpoint.
        Expects a very fast response because work is offloaded to SQS.
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        payload = {
            "data": "Simulating high traffic for loose coupling"
        }
        
        # Replace '/couplingl' with your actual loosely coupled API Gateway path
        with self.client.get("/loose", json=payload, headers=headers, catch_response=True) as response:
            
            # 202 Accepted is standard for queued tasks, 200 is also fine
            if response.status_code in [200, 202]:
                response.success()
            else:
                response.failure(f"API Error! Status: {response.status_code} | Body: {response.text}")