import json
import boto3
import os
from botocore.exceptions import ClientError

# =========================================================
# AWS RESOURCE INITIALIZATION
# =========================================================

dynamodb = boto3.resource('dynamodb')
ssm = boto3.client('ssm')

orders_table_name = os.environ.get('ORDERS_TABLE_NAME', 'OrdersTable')
idempotency_table_name = os.environ.get('IDEMPOTENCY_TABLE_NAME', 'IdempotencyTable')
ssm_parameter_name = os.environ.get('SSM_PARAMETER_NAME', '/orders/circuit-breaker-status')

orders_table = dynamodb.Table(orders_table_name)
idempotency_table = dynamodb.Table(idempotency_table_name)

# =========================================================
# CUSTOM EXCEPTION
# =========================================================

class CircuitBreakerOpenException(Exception):
    pass


# =========================================================
# HELPER: STANDARDIZED LOGGING
# =========================================================

def log(stage, message, data=None):
    """
    Unified structured logging for CloudWatch readability.
    """
    log_entry = {
        "STAGE": stage,
        "MESSAGE": message
    }

    if data:
        log_entry["DATA"] = data

    print(json.dumps(log_entry))


# =========================================================
# CIRCUIT BREAKER CHECK
# =========================================================

def check_circuit_breaker():

    log("CB-1", "Checking circuit breaker status from SSM")

    try:
        response = ssm.get_parameter(Name=ssm_parameter_name)

        status = response['Parameter']['Value'].strip().upper()

        log(
            "CB-2",
            "Circuit breaker status fetched",
            {"status": status}
        )

        return status

    except Exception as e:

        log(
            "CB-ERROR",
            "Failed to fetch circuit breaker status. Defaulting to CLOSED",
            {"error": str(e)}
        )

        return 'CLOSED'


# =========================================================
# MOCK DOWNSTREAM SERVICE
# =========================================================

def mock_downstream_api_call(order_data):


    log(
        "API-1",
        "Sending order to downstream service",
        {
            "order_id": order_data.get("order_id")
        }
    )

    # Simulated API call

    log(
        "API-2",
        "Downstream service completed successfully"
    )


# =========================================================
# MAIN LAMBDA HANDLER
# =========================================================

def lambda_handler(event, context):

    log("INIT", "Lambda invocation started")

    # =====================================================
    # STAGE 1 — CIRCUIT BREAKER
    # =====================================================

    circuit_status = check_circuit_breaker()

    if circuit_status == 'OPEN':

        log(
            "STOP",
            "Circuit breaker OPEN. Failing immediately."
        )

        raise CircuitBreakerOpenException(
            "System disabled via circuit breaker."
        )

    # =====================================================
    # STAGE 2 — PROCESS SQS RECORDS
    # =====================================================

    records = event.get('Records', [])

    log(
        "SQS-1",
        "Received SQS batch",
        {
            "record_count": len(records)
        }
    )

    for index, record in enumerate(records):

        try:

            log(
                "SQS-2",
                "Processing SQS record",
                {
                    "record_number": index + 1
                }
            )

            # =================================================
            # STAGE 3 — PARSE MESSAGE
            # =================================================

            message_body = json.loads(record['body'])

            order_id = message_body.get('order_id')
            idempotency_key = message_body.get('idempotency_key')
            customer_data = message_body.get('customer_data', {})
            items = message_body.get('items', [])

            log(
                "PARSE-1",
                "Message parsed successfully",
                {
                    "order_id": order_id,
                    "idempotency_key": idempotency_key
                }
            )

            # =================================================
            # STAGE 4 — VALIDATION
            # =================================================

            if not order_id or not idempotency_key:

                log(
                    "VALIDATION-ERROR",
                    "Missing required fields",
                    {
                        "order_id": order_id,
                        "idempotency_key": idempotency_key
                    }
                )

                continue

            # =================================================
            # STAGE 5 — IDEMPOTENCY CHECK
            # =================================================

            log(
                "IDEMPOTENCY-1",
                "Checking duplicate processing",
                {
                    "idempotency_key": idempotency_key
                }
            )

            try:

                idempotency_table.put_item(
                    Item={
                        'IdempotencyKey': idempotency_key
                    },
                    ConditionExpression='attribute_not_exists(IdempotencyKey)'
                )

                log(
                    "IDEMPOTENCY-2",
                    "Unique request confirmed"
                )

            except ClientError as e:

                if e.response['Error']['Code'] == 'ConditionalCheckFailedException':

                    log(
                        "IDEMPOTENCY-DUPLICATE",
                        "Duplicate message skipped",
                        {
                            "order_id": order_id
                        }
                    )

                    continue

                raise e

            # =================================================
            # STAGE 6 — SAVE ORDER
            # =================================================

            log(
                "DB-1",
                "Saving order to DynamoDB",
                {
                    "order_id": order_id
                }
            )

            orders_table.put_item(
                Item={
                    'OrderID': order_id,
                    'IdempotencyKey': idempotency_key,
                    'CustomerData': customer_data,
                    'Items': items,
                    'OrderStatus': 'PROCESSED'
                }
            )

            log(
                "DB-2",
                "Order saved successfully",
                {
                    "order_id": order_id
                }
            )

            # =================================================
            # STAGE 7 — DOWNSTREAM API
            # =================================================

            mock_downstream_api_call(message_body)

            # =================================================
            # STAGE 8 — SUCCESS
            # =================================================

            log(
                "SUCCESS",
                "Order fully processed",
                {
                    "order_id": order_id
                }
            )

        except Exception as e:

            log(
                "RECORD-FAILURE",
                "Critical failure processing record",
                {
                    "error": str(e)
                }
            )

            raise e

    # =====================================================
    # FINAL ACKNOWLEDGEMENT
    # =====================================================

    log(
        "COMPLETE",
        "Entire batch processed successfully"
    )

    return {
        'statusCode': 200,
        'body': json.dumps(
            'Order batch processed successfully.'
        )
    }