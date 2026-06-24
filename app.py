from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import base64

app = Flask(__name__)

def load_tokens():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens: {e}")
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
        
        # LOG: Tampilkan URL dan token (partial)
        app.logger.info(f"📤 Sending like to: {url}")
        app.logger.info(f"🔑 Token: {token[:20]}...")
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                response_text = await response.text()
                
                # LOG: Tampilkan response
                app.logger.info(f"📥 Response status: {response.status}")
                app.logger.info(f"📄 Response text: {response_text[:200]}")
                
                if response.status != 200:
                    app.logger.error(f"❌ Like failed: {response.status} - {response_text}")
                else:
                    app.logger.info(f"✅ Like success!")
                    
                return response.status
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name.upper()
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            app.logger.error("Failed to create protobuf message.")
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            app.logger.error("Encryption failed.")
            return None
            
        tasks = []
        tokens = load_tokens()
        if tokens is None:
            app.logger.error("Failed to load tokens.")
            return None
            
        # Hanya kirim 5 request dulu untuk test
        for i in range(5):  # Ganti dari 100 ke 5 untuk test
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # LOG hasil
        app.logger.info(f"Results: {results}")
        
        return results
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return None

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
        # Normalisasi server_name ke uppercase
        server_name = server_name.upper()
        
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            # ID dan semua region lainnya pake clientbp.ggpolarbear.com
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
            'ReleaseVersion': "OB53"
        }
        
        app.logger.info(f"Making request to: {url}")  # Debug log
        response = requests.post(url, data=edata, headers=headers, verify=False)
        
        if response.status_code != 200:
            app.logger.error(f"Request failed with status: {response.status_code}")
            return None
            
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
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
        "credit": "https://t.me/upuystrx",
        "message": "Welcome to the Free Fire Like API",
        "status": "API is running",
        "endpoints": "/like?uid=<uid> or /like?uid=<uid>&server_name=<server_name>",
        "example": "/like?uid=123456789 or /like?uid=123456789&server_name=bd"
})


@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID is required"}), 400

    if not uid.isdigit() or len(uid) < 8 or len(uid) > 15:
        return jsonify({"error": "Invalid UID. Must be 8-15 digits"}), 400

    try:
        tokens = load_tokens()
        if tokens is None or not tokens:
            return jsonify({"error": "Failed to load tokens."}), 500
        
        token = tokens[0]['token']
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
                return jsonify({"error": "Could not determine region from token"}), 400
        
        if not server_name:
            return jsonify({"error": "server_name could not be determined"}), 400
        
        app.logger.info(f"Processing UID: {uid}, Server: {server_name}")
        
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption of UID failed."}), 500

        # Get before likes
        before = make_request(encrypted_uid, server_name, token)
        if before is None:
            return jsonify({
                "error": "Failed to retrieve player info",
                "solution": "Check tokens.json or network connection"
            }), 500
        
        data_before = json.loads(MessageToJson(before))
        account_info_before = data_before.get('AccountInfo', {})
        before_like = int(account_info_before.get('Likes', 0) or 0)
        player_name = str(account_info_before.get('PlayerNickname', ''))
        player_uid = int(account_info_before.get('UID', 0) or 0)
        
        app.logger.info(f"✅ Player: {player_name}, UID: {player_uid}")
        app.logger.info(f"✅ Likes before: {before_like}")

        # Tentukan URL untuk like
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"
            
        app.logger.info(f"✅ Using URL: {url}")

        # Send like requests
        app.logger.info("🔄 Sending like requests...")
        requests_sent = asyncio.run(send_multiple_requests(uid, server_name, url))
        
        # Debug: Cek hasil request
        if requests_sent:
            success_count = sum(1 for r in requests_sent if r and r == 200)
            error_count = sum(1 for r in requests_sent if r and r != 200)
            app.logger.info(f"✅ Requests sent: {len(requests_sent)} total")
            app.logger.info(f"✅ Success: {success_count}, Failed: {error_count}")
            
            # Log beberapa error
            for i, result in enumerate(requests_sent[:5]):
                if result and result != 200:
                    app.logger.warning(f"Request {i+1} failed with status: {result}")
        else:
            app.logger.error("❌ No requests were sent!")

        # Get after likes
        app.logger.info("🔄 Getting after likes...")
        after = make_request(encrypted_uid, server_name, token)
        if after is None:
            return jsonify({"error": "Failed to retrieve player info after likes."}), 500
        
        data_after = json.loads(MessageToJson(after))
        account_info_after = data_after.get('AccountInfo', {})
        after_like = int(account_info_after.get('Likes', 0) or 0)
        
        app.logger.info(f"✅ Likes after: {after_like}")
        
        like_given = after_like - before_like
        app.logger.info(f"✅ Likes given: {like_given}")
        
        # Cek apakah UID sama (untuk memastikan tidak salah UID)
        after_uid = int(account_info_after.get('UID', 0) or 0)
        if after_uid != player_uid:
            app.logger.warning(f"⚠️ UID mismatch! Before: {player_uid}, After: {after_uid}")
        
        if like_given > 0:
            status_message = f"Successfully sent {like_given} likes!"
            status_code = 1
        elif like_given == 0:
            status_message = "No likes sent. Possible reasons:"
            status_message += "\n- Target account may have reached daily like limit"
            status_message += "\n- Token may not have permission to like"
            status_message += "\n- Already liked this account today"
            status_message += "\n- Server rejected the like requests"
            status_code = 2
        else:
            status_message = "Error: Likes decreased!"
            status_code = 0
        
        return jsonify({
            "credit": "https://t.me/paglu_dev",
            "status": status_code,
            "message": status_message,
            "PlayerNickname": player_name,
            "UID": player_uid,
            "Region": server_name,
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "RequestsTotal": len(requests_sent) if requests_sent else 0,
            "RequestsSuccess": success_count if requests_sent else 0,
            "RequestsFailed": error_count if requests_sent else 0
        })
    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500
        
if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
