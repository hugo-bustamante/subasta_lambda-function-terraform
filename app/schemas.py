from pydantic import BaseModel, EmailStr, validator


class ItemCreate(BaseModel):
    name: str
    start_price: float
    duration_minutes: int

class BidCreate(BaseModel):
    item_id: str
    user_email: EmailStr
    amount: float