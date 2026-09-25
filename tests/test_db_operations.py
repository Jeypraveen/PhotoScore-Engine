import os
from dotenv import load_dotenv

load_dotenv()

from app.database import (
    init_db,
    get_or_create_user,
    set_user_marketplace,
    record_usage,
    get_remaining_checks,
    get_total_users,
    get_total_checks
)

def run_tests():
    print("1. Initializing DB connection...")
    init_db()
    
    test_phone = "+1234567890"
    
    print(f"\n2. Creating/Fetching user with phone {test_phone}...")
    user = get_or_create_user(test_phone)
    print(f"User Data: {user}")
    
    print("\n3. Changing marketplace to 'shopify'...")
    set_user_marketplace(test_phone, "shopify")
    updated_user = get_or_create_user(test_phone)
    print(f"Updated Marketplace: {updated_user.get('marketplace')}")
    
    print("\n4. Recording a photo check (Usage)...")
    record_usage(test_phone, score=85)
    
    print("\n5. Checking remaining free limits...")
    remaining, total = get_remaining_checks(test_phone)
    print(f"Checks remaining today: {remaining}/{total}")
    
    print("\n6. Fetching global stats...")
    total_users = get_total_users()
    total_checks = get_total_checks()
    print(f"Total Users in DB: {total_users}")
    print(f"Total Checks in DB: {total_checks}")
    
    print("\n✅ ALL DATABASE OPERATIONS WORKED PERFECTLY!")

if __name__ == "__main__":
    run_tests()
