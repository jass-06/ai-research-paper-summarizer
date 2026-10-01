#!/usr/bin/env bash
# One-time creation of the processing Lambda. Run ../lambda/build.sh first.
# Fill in the placeholders. Tip: store GROQ_API_KEY / DATABASE_URL in AWS
# Secrets Manager for real production use instead of plain env vars.
set -euo pipefail
cd "$(dirname "$0")"

FUNCTION_NAME="paper-processor"
REGION="eu-central-1"
ROLE_ARN="arn:aws:iam::YOUR-ACCOUNT-ID:role/paper-processor-execution-role"
S3_BUCKET="YOUR-BUCKET-NAME"
DATABASE_URL="postgresql://USER:PASSWORD@YOUR-RDS-ENDPOINT:5432/ai_research"
GROQ_API_KEY="your-groq-key"
SUBNET_IDS="subnet-xxxx,subnet-yyyy"   # private subnets that can reach RDS
SECURITY_GROUP_IDS="sg-xxxx"           # must be allowed by the RDS security group on 5432

aws lambda create-function \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --runtime python3.12 \
  --architectures x86_64 \
  --role "$ROLE_ARN" \
  --handler lambda_function.lambda_handler \
  --zip-file fileb://../lambda/lambda_function.zip \
  --timeout 180 \
  --memory-size 1024 \
  --vpc-config "SubnetIds=$SUBNET_IDS,SecurityGroupIds=$SECURITY_GROUP_IDS" \
  --environment "Variables={STORAGE_BACKEND=s3,AWS_S3_BUCKET=$S3_BUCKET,DATABASE_URL=$DATABASE_URL,GROQ_API_KEY=$GROQ_API_KEY,ENABLE_ARXIV=true}"

echo "Lambda '$FUNCTION_NAME' created."
echo
echo "IMPORTANT networking note: a Lambda inside a VPC has NO internet access unless"
echo "its subnets route through a NAT Gateway. It needs internet to call the Groq API"
echo "and arXiv. Options: (a) private subnets + NAT Gateway (costs ~USD 30+/month),"
echo "(b) S3 Gateway VPC endpoint for S3 + NAT for Groq. See infra/deploy-aws.md."
