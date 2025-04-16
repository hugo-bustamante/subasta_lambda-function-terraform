from fastapi import FastAPI, HTTPException
from app.models import Item, Bid
from app.services import create_item, place_bid, get_auction_result
from app.schemas import ItemCreate, BidCreate

app = FastAPI()

@app.post("/items", response_model=Item)
def create_item_endpoint(item_data: ItemCreate):
    return create_item(item_data)

@app.post("/bids", response_model=Bid)
def place_bid_endpoint(bid_data: BidCreate):
    return place_bid(bid_data)

@app.get("/items/{item_id}")
def get_auction_result_endpoint(item_id: str):
    return get_auction_result(item_id)