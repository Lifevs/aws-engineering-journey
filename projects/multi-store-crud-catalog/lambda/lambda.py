import json
import boto3
import base64
import uuid
import logging
from datetime import datetime

# 1. Initialize the professional logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients outside the handler for connection reuse
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
rds_data = boto3.client('rds-data')

# Environment variables
BUCKET_NAME = 'catalog-product-images-191'
DYNAMO_TABLE = 'ProductMetadata'
AURORA_CLUSTER_ARN = ''
AURORA_SECRET_ARN = ''
DATABASE_NAME = 'database-1'

def lambda_handler(event, context):
    """Central router analyzing API Gateway requests."""
    http_method = event.get('httpMethod')
    path = event.get('resource')
    
    # Log the incoming traffic routing decision
    logger.info(f"Incoming Request: {http_method} {path}")
    
    try:
        if http_method == 'POST' and path == '/products/image':
            logger.info("Routing traffic to: handle_image_upload (S3 + DynamoDB)")
            return handle_image_upload(event)
        
        elif http_method == 'GET' and path == '/products':
            logger.info("Routing traffic to: handle_dynamo_lookup (DynamoDB)")
            return handle_dynamo_lookup(event)
            
        elif http_method == 'GET' and path == '/products/search':
            logger.info("Routing traffic to: handle_aurora_search (Aurora RDS)")
            return handle_aurora_search(event)
        
        else:
            logger.warning(f"Unmatched Route: {http_method} {path}")
            return respond(400, {"error": "Invalid route or method"})
            
    except Exception as e:
        # exc_info=True captures the exact line number and full Python stack trace in CloudWatch!
        logger.error(f"CRITICAL SYSTEM FAILURE: {str(e)}", exc_info=True)
        return respond(500, {"error": "Internal Server Error. Check CloudWatch logs."})

def handle_image_upload(event):
    """Extracts image, saves to S3, extracts metadata, saves to DynamoDB."""
    body = json.loads(event.get('body', '{}'))
    product_id = body.get('product_id', str(uuid.uuid4()))
    
    logger.info(f"[Process ID: {product_id}] Starting image processing payload extraction.")
    
    # 1. Decode the base64 image
    image_data = base64.b64decode(body['image_base64'])
    file_name = f"{uuid.uuid4()}.jpg"
    file_size_kb = round(len(image_data) / 1024, 2)
    
    logger.info(f"[Process ID: {product_id}] Image decoded. Size: {file_size_kb} KB. Target filename: {file_name}")
    
    # 2. Upload raw binary to S3
    logger.info(f"[Process ID: {product_id}] Attempting S3 PutObject to bucket: {BUCKET_NAME}")
    s3.put_object(Bucket=BUCKET_NAME, Key=file_name, Body=image_data, ContentType='image/jpeg')
    image_url = f"https://{BUCKET_NAME}.s3.amazonaws.com/{file_name}"
    logger.info(f"[Process ID: {product_id}] S3 Upload Successful. Generated URL: {image_url}")
    
    # 3. Extract/Generate Metadata and save to DynamoDB
    metadata = {
        'ProductID': product_id,
        'ImageURL': image_url,
        'FileSizeKB': str(file_size_kb), # Cast to string or Decimal for DynamoDB safety
        'UploadTimestamp': str(datetime.now())
    }
    
    logger.info(f"[Process ID: {product_id}] Attempting DynamoDB PutItem to table: {DYNAMO_TABLE}")
    table = dynamodb.Table(DYNAMO_TABLE)
    table.put_item(Item=metadata)
    logger.info(f"[Process ID: {product_id}] DynamoDB Save Successful. Transaction complete.")
    
    return respond(200, {"message": "Success", "metadata": metadata})

def handle_dynamo_lookup(event):
    """Direct, high-speed key-value lookup."""
    product_id = event.get('queryStringParameters', {}).get('product_id')
    logger.info(f"Executing fast NoSQL lookup for ProductID: {product_id}")
    
    table = dynamodb.Table(DYNAMO_TABLE)
    response = table.get_item(Key={'ProductID': product_id})
    
    if 'Item' in response:
        logger.info(f"Item found in DynamoDB: {product_id}")
    else:
        logger.warning(f"Item NOT found in DynamoDB: {product_id}")
        
    return respond(200, response.get('Item', {}))

def handle_aurora_search(event):
    """Executes relational queries via the Serverless Data API."""
    category = event.get('queryStringParameters', {}).get('category')
    logger.info(f"Executing relational search query for category: {category}")
    
    sql = "SELECT id, name, price FROM products WHERE category = :category AND stock > 0"
    
    logger.info(f"Transmitting SQL execution via Data API to cluster: {AURORA_CLUSTER_ARN}")
    response = rds_data.execute_statement(
        resourceArn=AURORA_CLUSTER_ARN,
        secretArn=AURORA_SECRET_ARN,
        database=DATABASE_NAME,
        sql=sql,
        parameters=[{'name': 'category', 'value': {'stringValue': category}}]
    )
    
    records = response.get('records', [])
    logger.info(f"Aurora query successful. Retrieved {len(records)} records.")
    
    return respond(200, {"results": records})

def respond(status_code, body):
    """Helper to format API Gateway responses with CORS headers."""
    logger.info(f"Dispatching HTTP {status_code} response to client.")
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*', 
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token',
            'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
        },
        'body': json.dumps(body)
    }