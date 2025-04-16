from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
from typing import Optional

class Item(BaseModel):
    id: str
    name: str
    start_price: Decimal
    end_time: str
    highest_bid: Decimal = Decimal("0.0")
    highest_bidder: Optional[str] = None

class Bid(BaseModel):
    item_id: str
    user_email: str
    amount: Decimal