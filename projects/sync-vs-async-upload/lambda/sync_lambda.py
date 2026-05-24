import base64
import boto3
import json
import os
import time
from email.parser import BytesParser
from email.policy import default

# Initialize AWS clients outside handler for container reuse
s3_client = boto3.client('s3')
UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET', 'aws-engineering-journey-uploads')

def lambda_handler(event, context):
    """
    Handles Synchronous File Upload:
    Parses multipart/form-data from API Gateway REST Proxy integration,
    extracts the binary stream, and saves it directly to Amazon S3.
    """
    start_time = time.time()
    print("Received API Gateway event headers and context metadata.")
    
    try:
        # 1. Extract and normalize content-type header
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        content_type = headers.get('content-type', '')
        
        if 'multipart/form-data' not in content_type:
            return respond(400, {"error": "Invalid Content-Type. Must be multipart/form-data"})
            
        # 2. Decode the raw base64 body sent by API Gateway
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body_bytes = base64.b64decode(body)
        else:
            body_bytes = body.encode('utf-8') if isinstance(body, str) else body
            
        # 3. Parse the multipart body using standard email library
        # We synthesize HTTP headers to allow the parser to handle multipart borders
        message_raw = f"Content-Type: {content_type}\r\n\r\n".encode('utf-8') + body_bytes
        msg = BytesParser(policy=default).parsebytes(message_raw)
        
        file_part = None
        for part in msg.iter_parts():
            if part.get_filename():
                file_part = part
                break
                
        if not file_part:
            return respond(400, {"error": "No file parameter found in multipart payload"})
            
        file_name = file_part.get_filename()
        file_content = file_part.get_content()
        
        # 4. Generate unique key in S3 to prevent collisions
        s3_key = f"sync-uploads/{int(time.time())}_{file_name}"
        
        # 5. Upload binary block to S3
        print(f"Uploading file '{file_name}' to S3 bucket '{UPLOAD_BUCKET}' with key '{s3_key}'...")
        s3_client.put_object(
            Bucket=UPLOAD_BUCKET,
            Key=s3_key,
            Body=file_content,
            ContentType=file_part.get_content_type()
        )
        
        duration = round(time.time() - start_time, 3)
        print(f"Direct S3 upload successful. Execution duration: {duration} seconds.")
        
        # Return upload success response
        return respond(200, {
            "status": "Success",
            "message": "File uploaded successfully via Synchronous Lambda.",
            "file_name": file_name,
            "s3_key": s3_key,
            "s3_bucket": UPLOAD_BUCKET,
            "size_bytes": len(file_content),
            "upload_duration_seconds": duration
        })
        
    except Exception as e:
        print(f"Exception encountered during sync-upload process: {str(e)}")
        return respond(500, {
            "status": "Error",
            "message": "Internal processing exception occurred during sync upload.",
            "error_details": str(e)
        })

def respond(status_code, body):
    """
    Synthesizes standard API Gateway integration proxy response.
    Includes strict CORS support.
    """
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"
        },
        "body": json.dumps(body)
    }
