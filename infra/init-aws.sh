#!/bin/bash
set -e

echo "Initializing LocalStack AWS resources..."

# Wait for LocalStack to be ready
while ! curl -s http://localhost:4566/_localstack/health | grep -q '"running"'; do
    sleep 2
done

# Create SQS queue
awslocal sqs create-queue --queue-name import-jobs

# Create S3 bucket
awslocal s3 mb s3://ecommerce-inventory-imports

# Create Secrets
awslocal secretsmanager create-secret \
    --name prod/jwt-secret \
    --secret-string "super-secret-jwt-key-change-in-production"

awslocal secretsmanager create-secret \
    --name prod/database-url \
    --secret-string "postgresql+psycopg://postgres:postgres@db:5432/inventory"

# Create CloudWatch log group
awslocal logs create-log-group --log-group-name ecommerce-api

echo "LocalStack initialization complete!"