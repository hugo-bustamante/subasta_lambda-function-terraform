import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timedelta
from decimal import Decimal
import uuid

from app.main import app

client = TestClient(app)

# Datos simulados para pruebas
mock_item_id = str(uuid.uuid4())
mock_item = {
    "id": mock_item_id,
    "name": "Test Item",
    "start_price": "100.0",
    "end_time": (datetime.utcnow() + timedelta(seconds=30)).isoformat(),
    "highest_bid": "0.0",
    "highest_bidder": None
}

def test_create_item():
    with patch("app.services.items_table.put_item") as mock_put:
        response = client.post("/items", json={
            "name": "Test Item",
            "start_price": 100.0,
            "duration_minutes": 1
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Item"
        mock_put.assert_called_once()
        return data["id"]

def test_valid_bid():
    mock_response_item = mock_item.copy()

    with patch("app.services.items_table.get_item", return_value={"Item": mock_response_item}), \
         patch("app.services.bids_table.put_item") as mock_put_bid, \
         patch("app.services.items_table.update_item") as mock_update:

        response = client.post("/bids", json={
            "item_id": mock_item_id,
            "user_email": "test@example.com",
            "amount": 150.0
        })

        assert response.status_code == 200
        data = response.json()
        assert data["user_email"] == "test@example.com"
        assert float(data["amount"]) == 150.0
        mock_put_bid.assert_called_once()
        mock_update.assert_called_once()

def test_invalid_bid_lower_amount():
    mock_item_high_bid = mock_item.copy()
    mock_item_high_bid["highest_bid"] = "200.0"

    with patch("app.services.items_table.get_item", return_value={"Item": mock_item_high_bid}):
        response = client.post("/bids", json={
            "item_id": mock_item_id,
            "user_email": "loser@example.com",
            "amount": 150.0
        })

        assert response.status_code == 400
        assert response.json()["detail"] == "Bid must be higher than current highest bid"

def test_get_auction_result_ongoing():
    item_ongoing = mock_item.copy()
    item_ongoing["end_time"] = (datetime.utcnow() + timedelta(seconds=60)).isoformat()

    with patch("app.services.items_table.get_item", return_value={"Item": item_ongoing}):
        response = client.get(f"/items/{mock_item_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "Auction is still ongoing"

def test_get_auction_result_ended():
    item_ended = mock_item.copy()
    item_ended["end_time"] = (datetime.utcnow() - timedelta(seconds=10)).isoformat()
    item_ended["highest_bidder"] = "winner@example.com"
    item_ended["highest_bid"] = "300.0"

    with patch("app.services.items_table.get_item", return_value={"Item": item_ended}), \
         patch("app.services.bids_table.query", return_value={"Items": [
             {"user_email": "winner@example.com"},
             {"user_email": "loser@example.com"}
         ]}), \
         patch("app.services.sns.create_topic", return_value={"TopicArn": "arn:aws:sns:..."}), \
         patch("app.services.sns.list_subscriptions_by_topic", return_value={"Subscriptions": [
             {"Endpoint": "winner@example.com", "SubscriptionArn": "arn:confirmed"},
             {"Endpoint": "loser@example.com", "SubscriptionArn": "arn:confirmed"},
         ]}), \
         patch("app.services.sns.publish") as mock_publish:

        response = client.get(f"/items/{mock_item_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "Auction ended"
        assert data["winner"] == "winner@example.com"
        assert float(data["winning_bid"]) == 300.0
        assert mock_publish.call_count == 2 