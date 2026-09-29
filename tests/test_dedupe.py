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
            "payload": {"payment": {"entity": {"id": "pay_123", "status": "captured", "amount": 29900, "currency": "INR", "notes": {"phone_number": "9999999999"}}}}
        }
    )
    
    # Expected to throw 500 so Razorpay retries
    assert response.status_code == 500
    # Also expected to have released both the event and the payment entity
    mock_release.assert_any_call("pay:pay_123")
    mock_release.assert_any_call("evt_456")
    assert mock_release.call_count == 2

@patch("app.main.verify_sig")
@patch("app.main.claim_event")
@patch("app.main.set_user_paid")
@patch("app.main.get_or_create_user")
def test_razorpay_double_event_types(mock_get_user, mock_set_paid, mock_claim, mock_verify):
    mock_verify.return_value = True
    
    # claim_event returns True on the first call (for the event id), True on the second (for the pay id)
    # On the second webhook, it returns True for the event id, but False for the pay id!
    mock_claim.side_effect = [True, True, True, False]
    
    mock_get_user.return_value = {"paid_until": None}
    mock_set_paid.return_value = True
    
    payload_captured = {
        "event": "payment.captured",
        "payload": {
            "payment": {"entity": {"id": "pay_999", "status": "captured", "amount": 29900, "currency": "INR", "notes": {"phone_number": "9999999999"}}}
        }
    }
    
    payload_paid = {
        "event": "payment_link.paid",
        "payload": {
            "payment_link": {"entity": {"id": "plink_999", "status": "paid", "amount": 29900, "currency": "INR"}},
            "payment": {"entity": {"id": "pay_999", "status": "captured", "amount": 29900, "currency": "INR", "notes": {"phone_number": "9999999999"}}}
        }
    }
    
    res1 = client.post("/payment/webhook", headers={"X-Razorpay-Event-Id": "evt_capture_1"}, json=payload_captured)
    assert res1.status_code == 200
    
    res2 = client.post("/payment/webhook", headers={"X-Razorpay-Event-Id": "evt_link_1"}, json=payload_paid)
    assert res2.status_code == 200
    
    # Verify that the user was upgraded exactly once despite two webhooks arriving
    mock_set_paid.assert_called_once()

