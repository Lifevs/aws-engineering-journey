import json
import random
import os
from locust import HttpUser, task, between, events

class ServerlessUploadPerformanceTester(HttpUser):
    """
    Locust Load Tester comparing:
    1. Synchronous Blocking Upload: Client -> API Gateway -> Lambda -> S3
    2. Asynchronous SQS Ingestion: Client -> API Gateway -> SQS Queue (absorbed instantly)
    """
    
    # Simulate a realistic delay between uploads (1 to 5 seconds per user)
    wait_time = between(1, 5)
    
    def on_start(self):
        """
        Executed when a virtual user is instantiated.
        Establishes paths and checks for the required local testing image.
        """
        self.sample_image_path = "sample_test.jpg"
        
        # Determine current working directory to help locate the sample file
        if not os.path.exists(self.sample_image_path):
            # Fallback path inside the subfolder structure
            self.sample_image_path = "load-testing/sample_test.jpg"

    @task(3)
    def test_sync_upload(self):
        """
        Fires a blocking multipart/form-data upload.
        Triggers: Client -> API Gateway -> Lambda -> S3
        This task is weighted higher (weight=3) to stress test concurrent compute.
        """
        try:
            with open(self.sample_image_path, "rb") as f:
                file_binary_data = f.read()
        except FileNotFoundError:
            # Generate dummy bytes if the file is missing to keep the test running
            file_binary_data = b"dummy_sample_test_image_bytes_content_here"

        # Unique name to bypass cache and identify load test files in S3
        dynamic_file_name = f"load_test_sync_{random.randint(100000, 999999)}.jpg"
        
        files = {
            'file': (dynamic_file_name, file_binary_data, 'image/jpeg')
        }

        # Mimic standard Google Chrome browser headers to bypass strict wafs
        headers = {
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # POST file as multipart data to the synchronous endpoint
        with self.client.post("/dev/sync", files=files, headers=headers, timeout=30, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Sync Upload Failed! Status: {response.status_code} | Body: {response.text[:200]}")

    @task(3)
    def test_async_upload(self):
        """
        Fires an instant non-blocking SQS queue write.
        Triggers: Client -> API Gateway -> SQS Queue (No active backend waiting)
        Translates a tiny dummy pixel image into base64 to respect the SQS threshold limit.
        """
        # A tiny base64 string representing a 1x1 black pixel image (approx 100 bytes)
        dummy_base64_image = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="

        payload = {
            "file_name": f"load_test_async_{random.randint(100000, 999999)}.jpg",
            "file_content": dummy_base64_image
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        # Send Base64 payload directly to API Gateway -> SQS endpoint
        with self.client.post("/prod/async", data=json.dumps(payload), headers=headers, catch_response=True) as response:
            if response.status_code == 200 and "MessageId" in response.text:
                response.success()
            else:
                response.failure(f"Async Ingestion Failed! Status: {response.status_code} | Body: {response.text[:200]}")
