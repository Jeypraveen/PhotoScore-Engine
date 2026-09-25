import requests

def run_cybersecurity_tests():
    print("\n--- CYBERSECURITY TESTS ---")
    url = "http://localhost:8000/api/analyze?marketplace=amazon"
    
    # 1. No API Key
    print("Test 1: Request with NO API Key...")
    r1 = requests.post(url, files={"file": ("dummy.jpg", b"fake image", "image/jpeg")})
    print(f"Result (Should be 400/403/422): {r1.status_code}")
    assert r1.status_code in [400, 403, 422]

    # 2. Bad API Key
    print("Test 2: Request with INVALID API Key...")
    r2 = requests.post(url, headers={"X-API-Key": "hacker123"}, files={"file": ("dummy.jpg", b"fake image", "image/jpeg")})
    print(f"Result (Should be 400/403/422): {r2.status_code}")
    assert r2.status_code in [400, 403, 422]
    
    print("CYBERSECURITY TESTS PASSED - Server is protected.")

if __name__ == "__main__":
    run_cybersecurity_tests()
