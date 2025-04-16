import boto3
import os
from dotenv import load_dotenv

load_dotenv()

sqs = boto3.client("sqs")
sns = boto3.client("sns")

SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL")
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")