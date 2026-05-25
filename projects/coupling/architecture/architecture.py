from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import APIGateway
from diagrams.aws.integration import SQS
from diagrams.aws.general import Client
from diagrams.aws.database import Dynamodb
from diagrams.aws.management import ParameterStore

# ---------------------------------------------------------
# 1. Tight Coupling Architecture Diagram
# ---------------------------------------------------------
with Diagram("Tight Coupling Architecture", filename="tight_coupling", show=False, direction="LR"):
    client = Client("Client Request")
    api = APIGateway("API Gateway\n(/couplingt)")

    with Cluster("Synchronous Dependency", direction="LR"):
        l1 = Lambda("Lambda 1\n(Orchestrator)")
        l2 = Lambda("Lambda 2\n(Worker)")

    # Flow
    client >> api >> l1

    # FIX: Changed bold=True to style="bold"
    l1 >> Edge(label="Direct Sync Call\n(Waits for response)", color="red", style="bold") >> l2
    l2 >> Edge(label="Returns Data or Fails", style="dashed", color="red") >> l1


# ---------------------------------------------------------
# 2. Loose Coupling Architecture Diagram
# ---------------------------------------------------------
with Diagram("Loose Coupling Architecture", filename="loose_coupling", show=False, direction="LR"):
    client_loose = Client("Client Request")
    api_loose = APIGateway("API Gateway\n(/loose)")

    with Cluster("Asynchronous Decoupling", direction="LR"):
        l1_loose = Lambda("Lambda 1\n(Producer)")
        queue = SQS("SQS Queue")
        l2_loose = Lambda("Lambda 2\n(Consumer)")

    # Flow
    client_loose >> api_loose >> l1_loose

    # FIX: Changed bold=True to style="bold"
    l1_loose >> Edge(label="Async Push\n(Returns 202 instantly)", color="darkgreen", style="bold") >> queue
    queue >> Edge(label="Event Trigger (Batch)", color="darkgreen") >> l2_loose


# ---------------------------------------------------------
# 3. Fault-Tolerant Architecture Diagram
# ---------------------------------------------------------
with Diagram("Fault-Tolerant Architecture", filename="fault_tolerant", show=False, direction="LR"):
    client_ft = Client("Producer")

    with Cluster("Asynchronous Ingestion"):
        queue_ft = SQS("Order Queue")
        dlq = SQS("Dead Letter Queue")

    with Cluster("Robust Processor"):
        processor = Lambda("Order Processor\n(Circuit Breaker + Idempotency)")
        ssm = ParameterStore("Circuit Breaker (SSM)")

    with Cluster("Storage"):
        idempotency_db = Dynamodb("Idempotency Table")
        orders_db = Dynamodb("Orders Table")

    external_api = Client("External API")

    # Connections
    client_ft >> queue_ft
    queue_ft >> Edge(label="3 Retries", color="firebrick", style="dashed") >> dlq

    queue_ft >> Edge(label="Trigger") >> processor

    processor >> Edge(label="1. Check CB", style="dashed") >> ssm
    processor >> Edge(label="2. Idempotency") >> idempotency_db
    processor >> Edge(label="3. Save Data") >> orders_db
    processor >> Edge(label="4. Call API", color="blue") >> external_api