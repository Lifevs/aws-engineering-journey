import unittest
import sys
import os
# Import your handler from your src/app.py file
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.app import lambda_handler

class TestLambdaLogic(unittest.TestCase):
    
    def test_successful_transformation(self):
        # 1. Define the MOCK PAYLOAD (The event)
        # This represents what VTL creates before it hits your Lambda
        mock_event = {
            "body_data": {"username": "Lokeshwara"},
            "client_ip": "192.168.1.1",
            "extracted_header": "GoldenJacketToken123"
        }
        
        # 2. Invoke the function
        response = lambda_handler(mock_event, {})
        
        # 3. Assert the outcome
        self.assertEqual(response['status'], "PROCESSED")
        self.assertIn("Hello Lokeshwara", response['message'])
        self.assertEqual(response['security_audit']['passed_header'], "GoldenJacketToken123")

if __name__ == '__main__':
    unittest.main()