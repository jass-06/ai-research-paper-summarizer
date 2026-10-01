# Deploying to AWS

There are two deployment tiers. Start with **Tier 1** — it is cheaper, simpler,
and already uses EC2, S3, RDS and CloudFront. Add **Tier 2** (Lambda) when you
want to demonstrate serverless processing.

| | Tier 1: EC2 + S3 + RDS + CloudFront | Tier 2: + Lambda |
|---|---|---|
| Processing | background task inside the EC2 container | AWS Lambda (async) |
| `LOCAL_PROCESSING` | `true` | `false` |
| Extra networking | none | NAT Gateway (Lambda in VPC needs internet for Groq/arXiv) |
| Rough cost (eu-central-1, small) | free tier / a few USD | + ~USD 30–35/month for NAT |

> **Region**: examples use `eu-central-1` (Frankfurt). Use one region for everything.
> **Cost safety**: create an AWS Budget alert (e.g. USD 10) before you start, and
> delete the NAT Gateway / RDS when you are done demoing.

---

## Tier 1

### 1. S3 bucket (private, for PDFs and results)
```bash
aws s3api create-bucket --bucket YOUR-BUCKET-NAME --region eu-central-1 \
  --create-bucket-configuration LocationConstraint=eu-central-1
aws s3api put-public-access-block --bucket YOUR-BUCKET-NAME \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```
Object layout: `uploads/…pdf`, `processed/…json`, `text/…txt`.

### 2. RDS PostgreSQL
- Console → RDS → Create database → PostgreSQL → Free tier template, `db.t4g.micro`.
- DB name `ai_research`; **Public access: No**; same VPC as your EC2 instance.
- Security group: allow inbound **5432 from the EC2 instance's security group** only.
- The backend creates the table on first start (or run `infra/rds-schema.sql`).

### 3. IAM role for EC2 (no access keys on the server)
- IAM → Policies → Create policy → paste `infra/iam-policy.json` (replace placeholders).
- IAM → Roles → Create role → trusted entity **EC2** → attach the policy.
- Attach the role to the instance (EC2 → Actions → Security → Modify IAM role).

### 4. EC2 instance running the container
- Launch Amazon Linux 2023, `t3.small` (t3.micro works but builds slowly).
- Security group: inbound 22 (your IP only) and 8000 (from CloudFront / your IP).
```bash
sudo dnf install -y docker git
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user && newgrp docker

git clone https://github.com/jass-06/ai-research-paper-summarizer.git
cd ai-research-paper-summarizer
cp .env.example .env
nano .env     # set GROQ_API_KEY, DATABASE_URL (RDS), AWS_S3_BUCKET, AWS_REGION
              # leave AWS_ACCESS_KEY_ID / SECRET empty — the IAM role is used

docker build -f backend/Dockerfile -t paperai .
docker run -d --name paperai --restart unless-stopped -p 8000:8000 --env-file .env paperai
curl localhost:8000/api/health
```
The container serves the React app **and** the API, so `http://EC2-PUBLIC-DNS:8000` already works.

### 5. CloudFront (HTTPS in front of everything)
Why: browsers block an HTTPS page from calling an HTTP API ("mixed content").
Putting CloudFront in front of the EC2 container gives you one HTTPS domain for both.

1. CloudFront → Create distribution → Origin domain: your EC2 **public DNS**, protocol HTTP, port 8000.
2. Default behaviour: Viewer protocol **Redirect HTTP to HTTPS**; Allowed methods **GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE**.
3. Cache policy **CachingDisabled**; Origin request policy **AllViewerExceptHostHeader**.
4. (Optional) add a second behaviour for `/assets/*` with **CachingOptimized** for fast static files.
5. Add `https://dxxxx.cloudfront.net` to `FRONTEND_ORIGIN` in `.env` and restart the container.

*Alternative (classic SPA hosting)*: put `frontend/dist` in a separate private S3 bucket with
Origin Access Control as the default origin, and add the EC2 origin under a `/api/*`
behaviour. Same result, static files served from S3.

---

## Tier 2: add AWS Lambda processing

1. **Networking first.** Lambda must be in the RDS VPC, and then it has no internet.
   - Create private subnets whose route table sends `0.0.0.0/0` to a **NAT Gateway**.
   - Add an **S3 Gateway VPC endpoint** (free) so S3 traffic doesn't go through NAT.
2. **Execution role**: trusted entity Lambda, attach `infra/lambda-execution-role-policy.json`.
3. **Build & create**:
   ```bash
   cd lambda && ./build.sh && cd ..
   nano infra/deploy-lambda.sh      # fill in placeholders
   ./infra/deploy-lambda.sh
   ```
4. Allow the Lambda's security group in the RDS security group (port 5432).
5. On EC2 set `LOCAL_PROCESSING=false` and `AWS_LAMBDA_FUNCTION_NAME=paper-processor`, restart.
6. Watch logs: CloudWatch → Log groups → `/aws/lambda/paper-processor`.

**Do not** also enable the S3 `ObjectCreated` trigger while the backend invokes Lambda
directly — every paper would be processed twice.

### Updating code later
```bash
git pull
docker build -f backend/Dockerfile -t paperai . && docker rm -f paperai
docker run -d --name paperai --restart unless-stopped -p 8000:8000 --env-file .env paperai
cd lambda && ./build.sh && aws lambda update-function-code \
  --function-name paper-processor --zip-file fileb://lambda_function.zip
```
