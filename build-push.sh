ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
REPO_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ecs-demo-app

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com
docker build --build-arg APP_VERSION=v1 -t $REPO_URI:v1 -t $REPO_URI:latest .
docker push $REPO_URI:v1
docker push $REPO_URI:latest
