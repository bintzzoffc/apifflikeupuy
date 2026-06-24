import requests
import json
import base64

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
API_URL = "https://xtytdtyj-jwt.up.railway.app/token"

def read_uidpass():
    with open(UIDPASS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def decode_token(token):
    """Decode JWT token untuk mendapatkan region"""
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
        data = json.loads(decoded_payload)
        return data
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

def fetch_token(uid, password):
    url = f"{API_URL}?uid={uid}&password={password}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        
        if token:
            # Decode token untuk dapat region
            decoded = decode_token(token)
            if decoded:
                region = decoded.get('lock_region', 'Unknown')
                print(f"✓ Token for UID {uid} - Region: {region}")
            return token
        return None
    except Exception as e:
        print(f"Error fetching token for UID {uid}: {e}")
        return None

def update_token_file(token_list):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(token_list, f, ensure_ascii=False, indent=4)

def main():
    uidpass_list = read_uidpass()
    print(f"📊 Found {len(uidpass_list)} accounts in uidpass.json")
    
    new_tokens = []
    for idx, item in enumerate(uidpass_list, 1):
        uid = item.get("uid")
        password = item.get("password")
        
        if not uid or not password:
            print(f"⚠️ Account {idx}: Missing uid or password, skipping...")
            continue
        
        print(f"\n🔄 Account {idx}/{len(uidpass_list)}")
        print(f"   UID: {uid}")
        
        token = fetch_token(uid, password)
        if token:
            new_tokens.append({"token": token})
            print(f"   ✅ Token obtained!")
        else:
            print(f"   ❌ Failed to get token")
    
    if new_tokens:
        update_token_file(new_tokens)
        print(f"\n✅ tokens.json updated with {len(new_tokens)} tokens")
    else:
        print("\n❌ No tokens updated. Check your uidpass.json")

if __name__ == "__main__":
    main()
