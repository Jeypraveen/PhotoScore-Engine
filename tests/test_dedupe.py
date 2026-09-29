import os
os.environ["META_APP_SECRET"] = "dummysecret"
os.environ["RAZORPAY_WEBHOOK_SECRET"] = "dummysecret"

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from postgrest.exceptions import APIError
client = TestClient(app)

@patch("app.main.verify_sig")
@patch("app.main.claim_event")
def test_webhook_db_error_on_claim(mock_claim, mock_verify):
    mock_verify.return_value = True
    # Simulate DB error during claim
    mock_claim.side_effect = Exception("DB went away")
    
    response = client.post(
        "/webhook",
        json={"entry": [{"changes": [{"value": {"messages": [{"id": "msg123", "from": "123", "type": "text", "text": {"body": "hi"}}]}}]}]}
    )
    # Expected to throw 503 so Meta retries
    assert response.status_code == 503
    assert "Database error" in response.json()["detail"]

@patch("app.main.verify_sig")
@patch("app.main.claim_event")
def test_razorpay_duplicate_event(mock_claim, mock_verify):
    mock_verify.return_value = True
    # Simulate duplicate event
    mock_claim.return_value = False
    
    response = client.post(
        "/payment/webhook",
        headers={"X-Razorpay-Event-Id": "evt_123"},
        json={"event": "payment.captured"}
    )
    # Expected to silently return 200 without processing
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

@patch("app.main.verify_sig")
@patch("app.main.claim_event")
@patch("app.main.release_event")
@patch("app.main.get_or_create_user")
def test_razorpay_failure_after_claim(mock_get_user, mock_release, mock_claim, mock_verify):
    mock_verify.return_value = True
    mock_claim.return_value = True
    
    # Simulate failure during the actual processing
    mock_get_user.side_effect = Exception("Failed to get user")
    
    response = client.post(
        "/payment/webhook",
        headers={"X-Razorpay-Event-Id": "evt_456"},
        json={
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"status": "captured", "amount": 29900, "currency": "INR", "notes": {"phone_number": "9999999999"}}}}
        }
    )
    
    # Expected to throw 500 so Razorpay retries
    assert response.status_code == 500
    # Also expected to have released the event
    mock_release.assert_called_once_with("evt_456")
