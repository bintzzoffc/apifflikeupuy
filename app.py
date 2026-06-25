from flask import Flask, request, jsonify
import asyncio
import urllib3
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import base64
import time
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError

# Disable insecure request warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

def load_tokens():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens: {e}")
        return None

def get_valid_token(tokens):
    """Cari token pertama yang format JWT-nya valid."""
    for t in tokens:
        token = t.get('token')
        if token and token.count('.') == 2:
            return token
    return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2022.3.47f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB54"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as response:
                if response.status != 200:
                    body = await response.text()
                    app.logger.error(f"Like Request failed: {response.status} | body={body[:200]}")
                    return None
                return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None

async def send_multiple_requests(uid, server_name, url, tokens):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            return 0
        
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            return 0
        
        tasks = []
        max_requests = min(100, len(tokens) * 5)
        app.logger.info(f"Sending {max_requests} like requests to {url}...")
        
        for i in range(max_requests):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success = sum(1 for r in results if r is not None and not isinstance(r, Exception))
        app.logger.warning(f"✅ Like requests accepted by server: {success}/{max_requests}")
        return success
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return 0

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def make_request(encrypt, server_name, token):
    try:
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
            
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "UnityPlayer/2022.3.47f1 (UnityWebRequest/1.0, libcurl/8.5.0-DEV)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2022.3.47f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB54"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=15)
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
        if decode is None:
            app.logger.error("Protobuf decoding returned None.")
        return decode
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Error decoding Protobuf data: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error during protobuf decoding: {e}")
        return None

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "credit": "https://t.me/paglu_dev",
        "message": "Welcome to the Free Fire Like API",
        "status": "API is running",
        "endpoints": "/like?uid=<uid> or /like?uid=<uid>&server_name=<server_name>",
        "example": "/like?uid=123456789 or /like?uid=123456789&server_name=bd"
    })

@app.route('/like', methods=['GET'])
async def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID is required"}), 400

    try:
        tokens = load_tokens()
        if tokens is None or not tokens:
            return jsonify({"error": "Failed to load tokens."}), 500
        
        token = get_valid_token(tokens)
        if not token:
            return jsonify({"error": "No valid token found in tokens.json"}), 500
        
        server_name = request.args.get("server_name", "").upper()
        if not server_name:
            try:
                payload = token.split('.')[1]
                payload += '=' * (-len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
                parsed_payload = json.loads(decoded_payload)
                server_name = parsed_payload.get('lock_region', '').upper()
            except Exception as e:
                app.logger.error(f"Error decoding token payload: {e}")
        
        if not server_name:
            return jsonify({"error": "server_name could not be determined from token or input"}), 400
        
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption of UID failed."}), 500

        # Get before likes count
        before = make_request(encrypted_uid, server_name, token)
        if before is None:
            return jsonify({"error": "Failed to retrieve player info. Token might be expired or invalid!"}), 500
        
        data_before = json.loads(MessageToJson(before))
        before_like = int(data_before.get('AccountInfo', {}).get('Likes', 0) or 0)
        app.logger.info(f"Likes before: {before_like}")

        # Determine URL based on server
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"

        # Send like requests
        success_count = await send_multiple_requests(uid, server_name, url, tokens)

        # Delay 5 detik agar server FF sempat update database like-nya
        app.logger.info("Waiting 5 seconds for server to update likes...")
        await asyncio.sleep(5)

        # Get after likes count
        after = make_request(encrypted_uid, server_name, token)
        if after is None:
            return jsonify({"error": "Failed to retrieve player info after likes. Token might be expired!"}), 500
        
        data_after = json.loads(MessageToJson(after))
        account_info = data_after.get('AccountInfo', {})
        after_like = int(account_info.get('Likes', 0) or 0)
        player_uid = int(account_info.get('UID', 0) or 0)
        player_name = str(account_info.get('PlayerNickname', ''))
        
        like_given = after_like - before_like
        
        app.logger.warning(f"Before: {before_like} | After: {after_like} | Given: {like_given}")
        
        return jsonify({
            "credit": "https://t.me/paglu_dev",
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "Region": server_name,
            "UID": player_uid,
            "status": 1 if like_given > 0 else 2
        })
    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
