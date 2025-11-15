"""
Simple test script for the Reporting API (Service 3).
Run this after starting the ingestion_api.py service and processor.py,
and after sending some events.
"""

import requests
import json

BASE_URL = "http://localhost:5000"


def test_stats_without_date():
    """Test getting stats for a site_id without date filter."""
    print("Test 1: Getting stats for site_id without date...")
    response = requests.get(f"{BASE_URL}/stats?site_id=site-abc-123")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


def test_stats_with_date():
    """Test getting stats for a site_id with date filter."""
    print("Test 2: Getting stats for site_id with date...")
    response = requests.get(f"{BASE_URL}/stats?site_id=site-abc-123&date=2025-11-12")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


def test_stats_missing_site_id():
    """Test getting stats without site_id parameter."""
    print("Test 3: Getting stats without site_id...")
    response = requests.get(f"{BASE_URL}/stats")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 400


def test_stats_invalid_date():
    """Test getting stats with invalid date format."""
    print("Test 4: Getting stats with invalid date format...")
    response = requests.get(f"{BASE_URL}/stats?site_id=site-abc-123&date=invalid-date")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}\n")
    return response.status_code == 400


def test_stats_no_data():
    """Test getting stats for a site_id with no data."""
    print("Test 5: Getting stats for site_id with no data...")
    response = requests.get(f"{BASE_URL}/stats?site_id=nonexistent-site")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}\n")
    return response.status_code == 200


if __name__ == "__main__":
    print("=" * 50)
    print("Testing Reporting API (Service 3)")
    print("=" * 50)
    print("Make sure the ingestion_api.py service is running!\n")
    print("Note: For meaningful results, send some events first using:")
    print("  python test_ingestion.py\n")
    
    try:
        results = []
        results.append(("Stats without date", test_stats_without_date()))
        results.append(("Stats with date", test_stats_with_date()))
        results.append(("Missing site_id", test_stats_missing_site_id()))
        results.append(("Invalid date format", test_stats_invalid_date()))
        results.append(("No data found", test_stats_no_data()))
        
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

