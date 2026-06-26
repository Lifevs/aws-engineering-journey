import json

def lambda_handler(event, context):
    """
    AWS Lambda handler optimized for Custom VTL Integrations.
    The 'event' object matches the exact JSON schema defined in your template.yaml VTL script.
    """
    # Log incoming payload for visibility via CloudWatch / local terminal logs
    print("Received transformed VTL event: ", json.dumps(event))
    
    # Extract values mapped by the VTL script
    body_data = event.get("body_data", {})
    custom_header = event.get("extracted_header", "NOT_PROVIDED")
    client_ip = event.get("client_ip", "UNKNOWN")
    
    # Execute backend business validation
    user_name = body_data.get("username", "Guest")
    
    # Processed payload returned cleanly back to API Gateway
    return {
        "status": "PROCESSED",
        "message": f"Hello {user_name}, your request has been successfully processed.",
        "security_audit": {
            "passed_header": custom_header,
            "origin_ip": client_ip
        }
    }