#!/bin/bash
export AWS_PAGER=""

FUNCTION_NAME="vpc-rds-proxy-processor-v2"
TOTAL_REQUESTS=1000
BATCH_SIZE=10
NUM_BATCHES=$((TOTAL_REQUESTS / BATCH_SIZE))

echo "Starting load test: Sending $TOTAL_REQUESTS total requests..."
echo "Executing in $NUM_BATCHES consecutive batches of $BATCH_SIZE to stay under your account limit."

for b in $(seq 1 $NUM_BATCHES); do
  for i in $(seq 1 $BATCH_SIZE); do
    # /dev/null discards the individual output files to avoid cluttering your drive
    aws lambda invoke \
      --function-name $FUNCTION_NAME \
      --cli-binary-format raw-in-base64-out \
      --payload '{"trigger": "bulk-load"}' \
      /dev/null &
  done
  
  wait # Blocks the script until the current batch of 10 finishes
  
  # Print a progress dot every 5 batches
  if [ $((b % 5)) -eq 0 ]; then
    echo "Processed $((b * BATCH_SIZE)) / $TOTAL_REQUESTS requests..."
  fi
done

echo "Done! Running a final validation query..."

# Execute one last single synchronous invocation to pull the final database metrics
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --cli-binary-format raw-in-base64-out \
  --payload '{"trigger": "metric-check"}' \
  final_report.json

echo "--- FINAL TEST REPORT ---"
cat final_report.json
rm final_report.json