from diagrams import Diagram, Cluster, Edge
from diagrams.aws.general import User
from diagrams.aws.network import APIGateway
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.database import Dynamodb, Aurora, ElastiCache

# Diagram configuration: filename, output format, and layout direction (Left to Right)
graph_attr = {
    "fontsize": "18",
    "pad": "0.5"
}

with Diagram("Multi-Store CRUD Catalog Architecture", show=False, direction="LR", graph_attr=graph_attr):
    
    # 1. The Entry Points
    client = User("Client App / Tester")
    api_gateway = APIGateway("API Gateway\n(REST API)")
    
    # 2. The Compute Engine
    central_router = Lambda("Central Router\n(Python 3.12)")
    
    # 3. The Data Layer (Grouped logically)
    with Cluster("Polyglot Persistence Storage"):
        s3_bucket = S3("S3\n(catalog-product-images-191)")
        dynamo_table = Dynamodb("DynamoDB\n(ProductMetadata)")
        aurora_cluster = Aurora("Aurora Serverless\n(database-1)")
        cache = ElastiCache("ElastiCache\n(Trending Hot Data)")

    # 4. Defining the Traffic Flow (The Arrows)
    
    # Client to API
    client >> Edge(label="HTTP GET/POST") >> api_gateway
    
    # API to Lambda Router
    api_gateway >> Edge(label="Proxy Integration") >> central_router
    
    # Lambda routing logic (using colors and labels for clarity)
    central_router >> Edge(label="POST /image\n(Heavy Binaries)", color="darkgreen") >> s3_bucket
    
    central_router >> Edge(label="GET/POST /products\n(Fast Key-Value)", color="blue") >> dynamo_table
    
    central_router >> Edge(label="GET /search\n(Complex SQL via Data API)", color="purple") >> aurora_cluster
    
    central_router >> Edge(label="GET /trending\n(Sub-millisecond reads)", color="darkorange") >> cache

print("✅ Diagram generated successfully! Check your folder for the PNG file.")