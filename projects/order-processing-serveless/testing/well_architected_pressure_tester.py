import json
import random
from datetime import datetime, timedelta

# ==========================================
# PRESSURE 1: SCALE (Performance Efficiency)
# Run via: locust -f well_architected_pressure_tester.py --host=https://YOUR_API_URL/dev
# ==========================================
if __name__ != "__main__":
    from locust import HttpUser, task, between

    class OrderPipelineTester(HttpUser):
        wait_time = between(0.1, 0.5) # Aggressive wait time to generate high RPS

        @task(3)
        def submit_car_order(self):
            """Simulates high-volume traffic to the Car queue"""
            payload = {
                "order_id": f"ORD-CAR-{random.randint(10000, 99999)}",
                "category": "car",
                "vehicle": random.choice(["Mustang", "Civic", "Corolla", "Model 3"])
            }
            self.client.post("/orders", json=payload, name="POST /orders (CAR)")

        @task(3)
        def submit_bike_order(self):
            """Simulates high-volume traffic to the Bike queue"""
            payload = {
                "order_id": f"ORD-BIK-{random.randint(10000, 99999)}",
                "category": "bike",
                "vehicle": random.choice(["Yamaha R1", "Kawasaki Ninja", "Ducati"])
            }
            self.client.post("/orders", json=payload, name="POST /orders (BIKE)")

        @task(1)
        def submit_poison_pill(self):
            """Injects 1 DLQ failure for every 6 successful orders to test scale of DLQ routing"""
            payload = {
                "order_id": f"ORD-ERR-{random.randint(10000, 99999)}",
                "category": "car",
                "vehicle": "FAIL_CAR"
            }
            self.client.post("/orders", json=payload, name="POST /orders (FAIL)")

# ==========================================
# PRESSURE 2: FAILURE (Reliability)
# Chaos Engineering via Boto3
# ==========================================
def inject_chaos_throttle_dynamodb(table_name="UnifiedOrdersTable-dev"):
    """
    Simulates a database failure by dropping DynamoDB capacity to 1 WCU.
    This will instantly cause ProvisionedThroughputExceededExceptions in your Lambda.
    """
    import boto3
    dynamodb = boto3.client('dynamodb')
    print(f"⚠️ INJECTING CHAOS: Throttling {table_name}...")
    try:
        # Switch from On-Demand to Provisioned with minimum capacity
        dynamodb.update_table(
            TableName=table_name,
            BillingMode='PROVISIONED',
            ProvisionedThroughput={
                'ReadCapacityUnits': 1,
                'WriteCapacityUnits': 1
            }
        )
        print("💥 Chaos Injected: Table is now severely throttled. Watch your DLQs fill up!")
    except Exception as e:
        print(f"Chaos injection failed (Table might already be provisioned): {e}")

# ==========================================
# PRESSURE 3: COST (Cost Optimization)
# Fetching impact via AWS Cost Explorer
# ==========================================
def check_pipeline_cost():
    """
    Queries AWS Cost Explorer for the daily cost of the services used in your pipeline.
    Run this 24 hours after your load test to see the financial impact of scale.
    """
    import boto3
    ce = boto3.client('ce')
    end_date = datetime.today().strftime('%Y-%m-%d')
    start_date = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    
    print(f"💸 Fetching Pipeline Costs for {start_date}...")
    
    response = ce.get_cost_and_usage(
        TimePeriod={'Start': start_date, 'End': end_date},
        Granularity='DAILY',
        Metrics=['UnblendedCost'],
        Filter={
            'Dimensions': {
                'Key': 'SERVICE',
                'Values': [
                    'AWS Lambda', 
                    'Amazon DynamoDB', 
                    'Amazon Simple Queue Service', 
                    'Amazon Simple Notification Service',
                    'Amazon API Gateway'
                ]
            }
        }
    )
    
    total_cost = 0
    for result in response['ResultsByTime']:
        amount = float(result['Total']['UnblendedCost']['Amount'])
        total_cost += amount
        print(f"Date: {result['TimePeriod']['Start']} | Pipeline Cost: ${amount:.4f}")

# ==========================================
# CLI Execution Router
# ==========================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "chaos":
            inject_chaos_throttle_dynamodb()
        elif command == "cost":
            check_pipeline_cost()
        else:
            print("Usage for standalone tools:")
            print("  python pressure_tester.py chaos  # Throttle DynamoDB")
            print("  python pressure_tester.py cost   # Check AWS Costs")
            print("\nUsage for Load Testing:")
            print("  locust -f pressure_tester.py --host=https://YOUR_API_ENDPOINT")
    else:
        print("Please specify a command: 'chaos', 'cost', or run via 'locust'.")