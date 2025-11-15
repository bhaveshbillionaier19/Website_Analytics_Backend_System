"""
Simple test script for the Ingestion API.
Run this after starting the ingestion_api.py service.
"""

import requests
import json

BASE_URL = "http://localhost:5000"


def test_valid_event():
    """Test sending a valid event."""
    print("Test 1: Sending valid event...")
    event = {
        "site_id": "site-abc-123",
        "event_type": "page_view",
        "path": "/pricing",
        "user_id": "user-xyz-789",
        "timestamp": "2025-11-12T19:30:01Z"
    }
    response = requests.post(f"{BASE_URL}/event", json=event)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200


def test_missing_site_id():
    """Test event with missing site_id."""
    print("Test 2: Sending event with missing site_id...")
    event = {
        "event_type": "page_view"
    }
    response = requests.post(f"{BASE_URL}/event", json=event)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 400


def test_missing_event_type():
    """Test event with missing event_type."""
    print("Test 3: Sending event with missing event_type...")
    event = {
        "site_id": "site-abc-123"
    }
    response = requests.post(f"{BASE_URL}/event", json=event)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 400


def test_invalid_json():
    """Test sending invalid JSON."""
    print("Test 4: Sending invalid JSON...")
    response = requests.post(
        f"{BASE_URL}/event",
        data="not valid json",
        headers={"Content-Type": "application/json"}
    )
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 400


def test_health_check():
    """Test health check endpoint."""
    print("Test 5: Checking health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Ingestion API")
    print("=" * 50)
    print("Make sure the ingestion_api.py service is running!\n")
    
    try:
        results = []
        results.append(("Valid event", test_valid_event()))
        results.append(("Missing site_id", test_missing_site_id()))
        results.append(("Missing event_type", test_missing_event_type()))
        results.append(("Invalid JSON", test_invalid_json()))
        results.append(("Health check", test_health_check()))
        
        print("=" * 50)
        print("Test Results:")
        print("=" * 50)
        for test_name, passed in results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {test_name}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to the service.")
        print("Please make sure ingestion_api.py is running on http://localhost:5000")
    except Exception as e:
        print(f"ERROR: {e}")

