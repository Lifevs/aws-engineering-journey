from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.network import APIGateway
from diagrams.aws.integration import SQS
from diagrams.aws.general import Client

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