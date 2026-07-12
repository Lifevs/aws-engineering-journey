# CodePipeline CI/CD (EC2-only) — CodeCommit → CodeBuild → CodeDeploy

Corrected architecture from your whiteboard sketch, EC2-only, with CodeArtifact for dependencies.

```
CodeCommit (push) --triggers--> CodePipeline
                                    |
                                    v
                              [Source stage]
                                    |
                                    v
                              [Build stage] --uses--> CodeArtifact (private deps)
                              (CodeBuild)
                                    |
                                    v
                          [Manual Approval stage]  (SNS notifies approver)
                                    |
                                    v
                              [Deploy stage]
                          (CodeDeploy -> EC2, ComputePlatform: Server)
```

## Files in this project

| File | Purpose |
|---|---|
| `infrastructure/pipeline-cfn.yaml` | CloudFormation stack: CodeCommit repo, CodeArtifact domain/repo, IAM roles, CodeBuild project, CodeDeploy app + deployment group, EC2 instance w/ CodeDeploy agent bootstrap, CodePipeline, EventBridge trigger |
| `buildspec.yml` | Tells CodeBuild how to log into CodeArtifact, install deps, run tests, build |
| `appspec.yml` | Tells CodeDeploy how to deploy to EC2 (file locations + lifecycle hooks) |
| `scripts/before_install.sh` | Stops old app, clears old deployment directory |
| `scripts/after_install.sh` | Installs production deps on the instance |
| `scripts/start_application.sh` | Starts the app via systemd |
| `scripts/validate_service.sh` | Health-checks the app after start |

## Deploy it

```bash
aws cloudformation deploy \
  --template-file infrastructure/pipeline-cfn.yaml \
  --stack-name my-ec2-app-pipeline \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
      KeyPairName=YOUR_KEYPAIR \
      VpcId=vpc-xxxxxxxx \
      SubnetId=subnet-xxxxxxxx
```

Then push your app code (including `buildspec.yml`, `appspec.yml`, and `scripts/`) into the CodeCommit repo the stack creates. A push to `main` fires the pipeline automatically via the EventBridge rule.

## Architecture validation summary (issues found in your sketch)

1. **Missing S3 artifact bucket** — mandatory for CodePipeline; added.
2. **Missing Manual Approval stage** — your notes said to add one, diagram didn't show it; added between Build and Deploy with SNS notification.
3. **Missing IAM roles** — 4 needed: CodePipeline, CodeBuild, CodeDeploy service role, EC2 instance role. All scoped least-privilege.
4. **Missing CodeDeploy Agent** — EC2 instances need the agent running to receive deployments; bootstrapped via `UserData` in the CloudFormation template.
5. **Missing `appspec.yml` + lifecycle scripts** — required for any EC2 CodeDeploy deployment; created.
6. **ComputePlatform explicitly set to `Server`** (not `Lambda`) on the CodeDeploy Application, matching your "EC2 only" requirement.
7. **Trigger mechanism made explicit** — EventBridge rule on `CodeCommit Repository State Change`, so pushing to `main` starts the pipeline automatically instead of relying on polling.

## Things to implement next

- [ ] Point `buildspec.yml`'s npm commands at your actual app (or swap to pip/maven/gradle if not Node.js)
- [ ] Create a real `myapp.service` systemd unit and bake it into the AMI or install it in `after_install.sh`
- [ ] Replace the single EC2 instance with an Auto Scaling Group for zero-downtime rolling deployments (`CodeDeployDefault.OneAtATime` works with ASGs too)
- [ ] Put the EC2 instance behind an Application Load Balancer + target group, and use `CodeDeployDefault.HalfAtATime` or a blue/green deployment config for zero-downtime releases
- [ ] Move hardcoded values (`CODEARTIFACT_DOMAIN`, ports, health check path) into SSM Parameter Store
- [ ] Add a rollback runbook — CloudFormation stack already enables `AutoRollbackConfiguration` on `DEPLOYMENT_FAILURE`
- [ ] Restrict SSH (port 22) in the security group to your IP/VPN, not `0.0.0.0/0`
- [ ] Add CloudWatch Alarms + SNS on pipeline/build failures

## Things worth learning (in order)

1. **CodeCommit → EventBridge → CodePipeline triggering** — understand push-based vs polling triggers
2. **`buildspec.yml` phases** (`install` / `pre_build` / `build` / `post_build`) and how CodeBuild artifacts pass to the next stage
3. **CodeArtifact auth flow** — `get-authorization-token` + `codeartifact login`, and how the 12-hour token expiry works in automated builds
4. **CodeDeploy `ComputePlatform`** differences: `Server` (EC2/on-prem) vs `Lambda` vs `ECS` — and why appspec.yml structure differs completely between them
5. **CodeDeploy lifecycle hooks** — the full event order: `ApplicationStop → DownloadBundle → BeforeInstall → Install → AfterInstall → ApplicationStart → ValidateService`
6. **Deployment configs** — `OneAtATime`, `HalfAtATime`, `AllAtOnce`, and custom configs for ASGs
7. **IAM trust policies vs permission policies** — why each AWS service (CodePipeline, CodeBuild, CodeDeploy, EC2) needs its own role with its own `AssumeRolePolicyDocument`
8. **Blue/green deployments** with CodeDeploy + ALB (natural next step after this pipeline works)
