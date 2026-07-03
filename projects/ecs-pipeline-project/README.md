# ECS Containerized App with ECR + CodePipeline Rolling Deploy

Containerizes a Node.js app, pushes it to ECR, deploys to ECS Fargate with a
task definition, and wires up CodePipeline (CodeCommit → CodeBuild → ECS
rolling deploy) so every commit ships automatically.

## Architecture (corrected)

```
                     CodePipeline
        ┌───────────────────────────────────────┐
        │  Source        Build          Deploy   │
CodeCommit ──▶ CodeBuild ──▶ ECR   ──▶ ECS Service │
        │  (git repo)   (docker build,   (Fargate, │
        │                push, tag,      rolling    │
        │                imagedefs.json) update)    │
        └───────────────────────────────────────┘
```

- **Source stage**: CodeCommit (swap for GitHub if you prefer — same pattern).
- **Build stage**: CodeBuild runs `buildspec.yml` — builds the Docker image,
  tags it with the short git commit hash *and* `latest`, pushes both to ECR,
  and emits `imagedefinitions.json` (this is what tells the ECS deploy action
  which new image to roll out).
- **Deploy stage**: CodePipeline's native `ECS` deploy action registers a new
  task definition revision pointing at the new image and calls
  `UpdateService`. The **rolling update** behavior is configured on the ECS
  **Service** itself (`MinimumHealthyPercent` / `MaximumPercent`), not on the
  pipeline — ECS gradually swaps old tasks for new ones based on those
  percentages.

---

## Files in this project

| File | Purpose |
|---|---|
| `app/index.js`, `app/package.json` | Minimal Express app with `/` and `/health` |
| `Dockerfile` | Multi-stage-ready Node 20 alpine build |
| `.dockerignore` | Keeps the build context small |
| `buildspec.yml` | CodeBuild instructions: build → tag → push → emit imagedefinitions.json |
| `task-definition.json` | Standalone ECS Fargate task def (for manual/CLI deploys) |
| `cloudformation/pipeline.yaml` | One-shot IaC: ECR, ECS cluster/service, CodeCommit, CodeBuild, CodePipeline, all IAM roles |

---

## Option A — Fully automated with CloudFormation (recommended)

### 1. Prerequisites
```bash
aws --version        # AWS CLI v2
aws sts get-caller-identity   # confirm you're authenticated
```
You'll need an existing VPC with at least 2 subnets that have a route to an
Internet Gateway (public subnets) — Fargate tasks in this demo get a public
IP directly rather than sitting behind a NAT/ALB, to keep the stack simple.

```bash
# Find a VPC and its public subnets
aws ec2 describe-vpcs --query "Vpcs[].VpcId"
aws ec2 describe-subnets --filters "Name=vpc-id,Values=<VPC_ID>" \
  --query "Subnets[].{Id:SubnetId,AZ:AvailabilityZone,Public:MapPublicIpOnLaunch}"
```

### 2. Deploy the stack
```bash
aws cloudformation deploy \
  --template-file cloudformation/pipeline.yaml \
  --stack-name ecs-demo-pipeline \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      AppName=ecs-demo-app \
      VpcId=<VPC_ID> \
      SubnetIds=<SUBNET_ID_1>,<SUBNET_ID_2>
```

### 3. Push your code to the new CodeCommit repo
```bash
# Get the clone URL
aws cloudformation describe-stacks --stack-name ecs-demo-pipeline \
  --query "Stacks[0].Outputs[?OutputKey=='RepositoryCloneUrlHttp'].OutputValue" --output text

# One-time: set up git-remote-codecommit or IAM git credentials, then:
git init
git add app Dockerfile .dockerignore buildspec.yml
git commit -m "Initial commit"
git branch -M main
git remote add origin <CLONE_URL_FROM_ABOVE>
git push -u origin main
```
Pushing to `main` automatically triggers the pipeline (CodeCommit → EventBridge → CodePipeline).

### 4. Watch it run
See the **Test / Verify** section below.

---

## Option B — Manual, step by step (good for learning each piece)

### 1. Create the ECR repo
```bash
aws ecr create-repository --repository-name ecs-demo-app
```

### 2. Build and push the image manually
```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=us-east-1
REPO_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/ecs-demo-app

aws ecr get-login-password --region $REGION | \
  docker login --username AWS --password-stdin $ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

docker build --build-arg APP_VERSION=v1 -t $REPO_URI:v1 -t $REPO_URI:latest .
docker push $REPO_URI:v1
docker push $REPO_URI:latest
```

### 3. Create the ECS cluster
```bash
aws ecs create-cluster --cluster-name ecs-demo-cluster
```

### 4. Create the execution role (if you don't already have one)
```bash
aws iam create-role --role-name ecsTaskExecutionRole \
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"ecs-tasks.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }'
aws iam attach-role-policy --role-name ecsTaskExecutionRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

### 5. Register the task definition
Edit `task-definition.json`, replacing `<AWS_ACCOUNT_ID>` and `<REGION>`, then:
```bash
aws logs create-log-group --log-group-name /ecs/ecs-demo-app
aws ecs register-task-definition --cli-input-json file://task-definition.json
```

### 6. Create the service (rolling update is the default deployment controller)
```bash
aws ecs create-service \
  --cluster ecs-demo-cluster \
  --service-name ecs-demo-app-service \
  --task-definition ecs-demo-app \
  --desired-count 2 \
  --launch-type FARGATE \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=50" \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_ID_1>,<SUBNET_ID_2>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}"
```

### 7. Wire up CodePipeline (console is fastest for a one-off manual setup)
AWS Console → CodePipeline → Create pipeline → Source: CodeCommit/GitHub →
Build: CodeBuild (point it at `buildspec.yml`) → Deploy: **Amazon ECS**,
select your cluster/service, and set the image definitions file to
`imagedefinitions.json`.

---

## Test / Verify commands

### Confirm the image landed in ECR
```bash
aws ecr describe-images --repository-name ecs-demo-app \
  --query "sort_by(imageDetails,& imagePushedAt)[-5:].{Tag:imageTags,Pushed:imagePushedAt}"
```

### Watch the pipeline run
```bash
aws codepipeline get-pipeline-state --name ecs-demo-app-pipeline
aws codepipeline list-pipeline-executions --pipeline-name ecs-demo-app-pipeline --max-results 5
```

### Watch the ECS rolling deployment happen live
```bash
watch -n 5 'aws ecs describe-services --cluster ecs-demo-cluster --services ecs-demo-app-service \
  --query "services[0].deployments[].{Status:status,Desired:desiredCount,Running:runningCount,Pending:pendingCount,TaskDef:taskDefinition}"'
```
During a rolling update you'll see two deployment entries briefly — `PRIMARY`
(new task def, ramping up) and `ACTIVE` (old task def, draining down) — until
only `PRIMARY` remains at full `desiredCount`.

### List running tasks and their IPs
```bash
TASK_ARNS=$(aws ecs list-tasks --cluster ecs-demo-cluster --service-name ecs-demo-app-service --query "taskArns" --output text)
aws ecs describe-tasks --cluster ecs-demo-cluster --tasks $TASK_ARNS \
  --query "tasks[].{Task:taskArn,LastStatus:lastStatus,HealthStatus:healthStatus}"

# Get a public IP to hit directly (since there's no ALB in this demo)
ENI_ID=$(aws ecs describe-tasks --cluster ecs-demo-cluster --tasks $(echo $TASK_ARNS | cut -d' ' -f1) \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value" --output text)
aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID \
  --query "NetworkInterfaces[0].Association.PublicIp" --output text
```

### Hit the app to confirm the new version is live
```bash
curl http://<PUBLIC_IP>:3000/
curl http://<PUBLIC_IP>:3000/health
# Response includes "version": "<commit-hash>" so you can confirm which
# build is actually serving traffic — critical for proving the rolling
# deploy worked, not just that the pipeline turned green.
```

### Prove a rolling update actually replaces tasks (not a restart)
```bash
# Before your next push, note current task ARNs:
aws ecs list-tasks --cluster ecs-demo-cluster --service-name ecs-demo-app-service --query "taskArns"

# Push a code change, wait for the pipeline to finish, then re-run the same
# command — task ARNs should have changed (new tasks replaced old ones),
# while desiredCount never dropped below minimumHealthyPercent of the total.
```

### Roll back manually if needed
```bash
# List task def revisions
aws ecs list-task-definitions --family-prefix ecs-demo-app --sort DESC

# Point the service back at a previous revision
aws ecs update-service --cluster ecs-demo-cluster --service ecs-demo-app-service \
  --task-definition ecs-demo-app:<PREVIOUS_REVISION_NUMBER>
```

### Tail application logs
```bash
aws logs tail /ecs/ecs-demo-app --follow
```

---

## What this demonstrates end-to-end

1. Docker image build reproducibility (`docker build` locally == what CodeBuild runs)
2. Image immutability/versioning via commit-hash tags in ECR
3. IaC-driven infra (cluster, service, roles, pipeline all from one template)
4. CI/CD trigger-on-push via CodeCommit → CodePipeline
5. Zero-downtime rolling deployment mechanics (`minimumHealthyPercent`/`maximumPercent`)
6. Observability: CloudWatch Logs, `describe-services` deployment status, ECR image history
7. Manual rollback path via task definition revisions

## Cleanup (avoid ongoing charges)
```bash
aws cloudformation delete-stack --stack-name ecs-demo-pipeline
# ECR repos aren't always auto-deleted if non-empty; force-delete if needed:
aws ecr delete-repository --repository-name ecs-demo-app --force
```
