import boto3
import os
from dotenv import load_dotenv

load_dotenv()

DYNAMODB_TABLE_ITEMS = os.getenv("DYNAMODB_TABLE_ITEMS", "AuctionItems")
DYNAMODB_TABLE_BIDS = os.getenv("DYNAMODB_TABLE_BIDS", "AuctionBids")

dynamodb = boto3.resource("dynamodb")

items_table = dynamodb.Table(DYNAMODB_TABLE_ITEMS)
bids_table = dynamodb.Table(DYNAMODB_TABLE_BIDS)