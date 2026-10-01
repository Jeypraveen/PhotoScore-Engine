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
@patch("app.main.apply_payment_rpc")
def test_razorpay_failure_after_claim(mock_apply, mock_release, mock_claim, mock_verify):
    mock_verify.return_value = True
    mock_claim.return_value = True
    
    # Simulate failure during the actual processing
    mock_apply.side_effect = Exception("Failed to apply payment")
    
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
    mock_apply.assert_called_once_with("pay:pay_123", "919999999999", 30)

@patch("app.main.verify_sig")
@patch("app.main.claim_event")
@patch("app.main.apply_payment_rpc")
def test_razorpay_double_event_types(mock_apply, mock_claim, mock_verify):
    mock_verify.return_value = True
    mock_claim.return_value = True
    
    # apply_payment_rpc returns date string on first success, None on second (duplicate)
    mock_apply.side_effect = ["2024-12-01T00:00:00Z", None]
    
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
    
    # Verify that the atomic RPC was called twice (once per webhook payload)
    assert mock_apply.call_count == 2

