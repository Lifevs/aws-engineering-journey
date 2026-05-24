import base64
import boto3
import json
import os
import time

# Initialize AWS clients outside handler for reuse
s3_client = boto3.client('s3')
UPLOAD_BUCKET = os.environ.get('UPLOAD_BUCKET', 'aws-engineering-journey-uploads')

def lambda_handler(event, context):
    """
    Handles Asynchronous SQS Ingestion:
    Triggered by SQS Queue Event. Processes batch of records,
    decodes base64-encoded files in SQS messages, and stores them in S3.
    """
    print(f"Triggered by SQS event. Processing {len(event.get('Records', []))} record(s)...")
    
    success_count = 0
    failure_count = 0
    
    for record in event.get('Records', []):
        message_id = record.get('messageId')
        print(f"Processing SQS message: {message_id}")
        
        try:
            # 1. Parse JSON body from SQS message
            message_body = json.loads(record.get('body', '{}'))
            file_name = message_body.get('file_name')
            file_content_base64 = message_body.get('file_content')
            
            if not file_name or not file_content_base64:
                print(f"Skipping record {message_id}: Missing 'file_name' or 'file_content'.")
                failure_count += 1
                continue
                
            # 2. Decode the Base64 file string to binary bytes
            print(f"Decoding base64 stream for file: {file_name}")
            decoded_file_bytes = base64.b64decode(file_content_base64)
            
            # 3. Create unique target S3 key
            s3_key = f"async-uploads/{int(time.time())}_{file_name}"
            
            # 4. Save decoded binary stream to S3
            print(f"Uploading file '{file_name}' to S3 bucket '{UPLOAD_BUCKET}' with key '{s3_key}'...")
            s3_client.put_object(
                Bucket=UPLOAD_BUCKET,
                Key=s3_key,
                Body=decoded_file_bytes,
                ContentType="image/jpeg" if file_name.lower().endswith(('.jpg', '.jpeg')) else "application/octet-stream"
            )
            
            print(f"Successfully processed message {message_id}. File saved: {s3_key}")
            success_count += 1
            
        except Exception as e:
            print(f"Failed to process message {message_id} due to exception: {str(e)}")
            failure_count += 1
            # In production, throwing an error here will return the message to SQS
            # so that it can be retried or sent to a Dead Letter Queue (DLQ).
            raise e
            
    print(f"SQS Processing batch finished. Success: {success_count}, Failures: {failure_count}.")
    return {
        "status": "BatchComplete",
        "processed_records": len(event.get('Records', [])),
        "success_count": success_count,
        "failure_count": failure_count
    }
