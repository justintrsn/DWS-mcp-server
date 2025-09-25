#!/usr/bin/env python3
"""
Test script for database switching functionality.
Tests the API endpoints for listing, switching, and testing database profiles.
"""

import requests
import json
import time
import sys

# Configuration
BASE_URL = "http://localhost:8080"
HEADERS = {"Content-Type": "application/json"}

def print_response(response, title):
    """Pretty print API response."""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(f"Status: {response.status_code}")
    try:
        data = response.json()
        print(f"Response:\n{json.dumps(data, indent=2)}")
    except:
        print(f"Raw Response: {response.text}")
    print()

def test_health():
    """Test basic health endpoint."""
    print("🏥 Testing Health Endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print_response(response, "Health Check")
    return response.status_code == 200

def test_list_profiles():
    """Test listing database profiles."""
    print("📋 Testing List Database Profiles...")
    response = requests.get(f"{BASE_URL}/api/database/list")
    print_response(response, "Database Profiles List")
    return response.status_code == 200, response.json() if response.status_code == 200 else None

def test_current_profile():
    """Test getting current database profile."""
    print("📍 Testing Current Database Profile...")
    response = requests.get(f"{BASE_URL}/api/database/current")
    print_response(response, "Current Database Profile")
    return response.status_code == 200, response.json() if response.status_code == 200 else None

def test_database_connection(profile_name, timeout=10):
    """Test connection to a specific database profile."""
    print(f"🔌 Testing Connection to '{profile_name}' Profile...")
    payload = {
        "profile": profile_name,
        "timeout": timeout
    }
    response = requests.post(f"{BASE_URL}/api/database/test",
                           json=payload, headers=HEADERS)
    print_response(response, f"Connection Test - {profile_name}")
    return response.status_code == 200, response.json() if response.status_code == 200 else None

def test_switch_profile(profile_name, validate_connection=True):
    """Test switching to a different database profile."""
    print(f"🔄 Testing Switch to '{profile_name}' Profile...")
    payload = {
        "profile": profile_name,
        "validate_connection": validate_connection,
        "force": False
    }
    response = requests.post(f"{BASE_URL}/api/database/switch",
                           json=payload, headers=HEADERS)
    print_response(response, f"Profile Switch - {profile_name}")
    return response.status_code == 200, response.json() if response.status_code == 200 else None

def test_database_health():
    """Test database-specific health endpoint."""
    print("🏥 Testing Database Health Endpoint...")
    response = requests.get(f"{BASE_URL}/health/database")
    print_response(response, "Database Health")
    return response.status_code == 200

def main():
    """Run all database switching tests."""
    print("🚀 PostgreSQL MCP Server - Database Switching Tests")
    print("=" * 60)

    failed_tests = []

    # Test 1: Basic health check
    if not test_health():
        failed_tests.append("Health Check")
        print("❌ Health check failed. Server may not be running.")
        return

    # Test 2: List available profiles
    success, profiles_data = test_list_profiles()
    if not success:
        failed_tests.append("List Profiles")
        print("❌ Failed to list database profiles")
        return

    available_profiles = list(profiles_data.get("profiles", {}).keys()) if profiles_data else []
    print(f"✅ Found {len(available_profiles)} database profiles: {available_profiles}")

    # Test 3: Get current profile
    success, current_data = test_current_profile()
    if not success:
        failed_tests.append("Current Profile")
    else:
        current_profile = current_data.get("name") if isinstance(current_data, dict) else None
        print(f"✅ Current profile: {current_profile or 'None'}")

    # Test 4: Database health
    if not test_database_health():
        failed_tests.append("Database Health")

    # Test 5: Test connections to available profiles
    if available_profiles:
        for profile in available_profiles:
            profile_data = profiles_data["profiles"][profile]
            if profile_data.get("enabled", False):
                print(f"\n📍 Testing enabled profile: {profile}")
                success, test_result = test_database_connection(profile)
                if not success:
                    failed_tests.append(f"Connection Test - {profile}")
                else:
                    connection_success = test_result.get("success", False)
                    if connection_success:
                        print(f"✅ Connection to {profile} successful")

                        # Test 6: Try switching to this profile
                        success, switch_result = test_switch_profile(profile)
                        if success and switch_result.get("success", False):
                            print(f"✅ Successfully switched to {profile}")

                            # Verify the switch worked
                            time.sleep(1)
                            success, verify_data = test_current_profile()
                            if success and isinstance(verify_data, dict):
                                current_name = verify_data.get("name")
                                if current_name == profile:
                                    print(f"✅ Switch verified: currently using {current_name}")
                                else:
                                    print(f"⚠️  Switch may not have worked: expected {profile}, got {current_name}")
                        else:
                            failed_tests.append(f"Profile Switch - {profile}")
                            print(f"❌ Failed to switch to {profile}")
                    else:
                        print(f"⚠️  Connection test failed for {profile}: {test_result.get('message', 'Unknown error')}")
            else:
                print(f"⏭️  Skipping disabled profile: {profile}")

    # Test 7: Test error handling - try switching to non-existent profile
    print(f"\n🧪 Testing Error Handling...")
    success, error_result = test_switch_profile("non_existent_profile")
    if not success or not error_result.get("success", True):
        print("✅ Error handling works correctly for invalid profiles")
    else:
        failed_tests.append("Error Handling")
        print("❌ Error handling failed - invalid profile was accepted")

    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")

    total_tests = 7
    passed_tests = total_tests - len(failed_tests)

    if failed_tests:
        print(f"❌ {len(failed_tests)} test(s) failed:")
        for test in failed_tests:
            print(f"   • {test}")
    else:
        print("✅ All tests passed!")

    print(f"\nResults: {passed_tests}/{total_tests} tests passed")

    if failed_tests:
        sys.exit(1)
    else:
        print("\n🎉 Database switching functionality is working correctly!")
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to the MCP server. Make sure it's running on localhost:8081")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)