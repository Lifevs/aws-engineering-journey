import time
from locust import HttpUser, task, between

class TightCouplingLoadTest(HttpUser):
    # Simulate a user waiting between 1 to 2 seconds between requests
    wait_time = between(1, 2)

    @task
    def test_tight_coupling_endpoint(self):
        """
        Sends a GET request to the /couplingt endpoint.
        Measures response time and tracks failure rates.
        """
        headers = {
            "Content-Type": "application/json"
        }
        
        # We wrap the request to log custom performance metrics if needed
        start_time = time.time()
        
        with self.client.get("/couplingt", headers=headers, catch_response=True) as response:
            duration = time.time() - start_time
            
            if response.status_code == 200:
                response.success()
            elif response.status_code == 502 or response.status_code == 500:
                # This captures when Lambda 2 breaks or times out, causing Lambda 1 to fail
                response.failure(f"Tightly-coupled failure detected! Status Code: {response.status_code} | Response: {response.text}")
            else:
                response.failure(f"Unexpected error: {response.status_code}")