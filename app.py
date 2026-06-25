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
import logging
import sys

app = Flask(__name__)

# Setup logging
logging.basicConfig(level=logging.INFO)
app.logger.setLevel(logging.INFO)

# Tambahkan handler untuk console
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)

def load_tokens():
    try:
        with open("tokens.json", "r") as f:
            tokens = json.load(f)
        app.logger.info(f"Loaded {len(tokens)} tokens")
        return tokens
    except FileNotFoundError:
        app.logger.error("tokens.json not found!")
        return None
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

async def send_request(encrypted_uid, token, url, index):
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
            async with session.post(url, data=edata, headers=headers, timeout=30) as response:
                if response.status != 200:
                    app.logger.error(f"Request {index} failed with status code: {response.status} for URL: {url}")
                    return {"index": index, "status": response.status, "success": False}
                app.logger.debug(f"Request {index} successful for URL: {url}")
                return {"index": index, "status": 200, "success": True}
    except asyncio.TimeoutError:
        app.logger.error(f"Timeout for URL: {url} at request {index}")
        return {"index": index, "status": None, "success": False, "error": "timeout"}
    except Exception as e:
        app.logger.error(f"Exception in send_request {index}: {e}")
        return {"index": index, "status": None, "success": False, "error": str(e)}

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            app.logger.error("Failed to create protobuf message.")
            return []
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            app.logger.error("Encryption failed.")
            return []
        
        tokens = load_tokens()
        if tokens is None or len(tokens) == 0:
            app.logger.error("Failed to load tokens or no tokens available.")
            return []
        
        # Use ALL tokens for sending likes (not just 100)
        total_tokens = len(tokens)
        app.logger.info(f"Sending {total_tokens} like requests to URL: {url}")
        
        tasks = []
        for i, token_data in enumerate(tokens):
            token = token_data["token"]
            tasks.append(send_request(encrypted_uid, token, url, i + 1))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successful requests
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("success", False))
        app.logger.info(f"Successfully sent {success_count} likes out of {total_tokens}")
        
        return {
            "total_requests": total_tokens,
            "success_count": success_count,
            "failed_count": total_tokens - success_count,
            "details": results
        }
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return {"error": str(e)}

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
        url = get_player_personal_show_url(server_name)
        app.logger.info(f"GetPlayerPersonalShow URL: {url}")
        
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
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=30)
        
        if response.status_code != 200:
            app.logger.error(f"GetPlayerPersonalShow failed with status: {response.status_code}")
            return None
            
        binary = response.content
        decode = decode_protobuf(binary)
        if decode is None:
            app.logger.error("Protobuf decoding returned None.")
        return decode
    except requests.exceptions.Timeout:
        app.logger.error("Timeout in make_request")
        return None
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def get_player_personal_show_url(server_name):
    """Get URL for GetPlayerPersonalShow based on region"""
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"ID", "IDN", "INDONESIA"}:
        return "https://client.id.freefiremobile.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"

def get_like_profile_url(server_name):
    """Get URL for LikeProfile based on region"""
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/LikeProfile"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/LikeProfile"
    elif server_name in {"ID", "IDN", "INDONESIA"}:
        return "https://client.id.freefiremobile.com/LikeProfile"
    else:
        return "https://clientbp.ggpolarbear.com/LikeProfile"

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
        "example": "/like?uid=123456789 or /like?uid=123456789&server_name=id",
        "supported_regions": ["IND", "BR", "US", "SAC", "NA", "ID", "IDN"]
    })

@app.route('/like', methods=['GET'])
def handle_requests():
    try:
        uid = request.args.get("uid")
        if not uid:
            return jsonify({"error": "UID is required"}), 400

        # Validate UID is numeric
        if not uid.isdigit():
            return jsonify({"error": "UID must be numeric"}), 400

        tokens = load_tokens()
        if tokens is None or len(tokens) == 0:
            return jsonify({"error": "Failed to load tokens or tokens.json is empty."}), 500
        
        token = tokens[0]['token']
        total_tokens = len(tokens)
        
        # Get server_name from request or token
        server_name = request.args.get("server_name", "").upper()
        
        if not server_name:
            try:
                payload = token.split('.')[1]
                payload += '=' * (-len(payload) % 4)
                decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
                parsed_payload = json.loads(decoded_payload)
                server_name = parsed_payload.get('lock_region', '').upper()
                app.logger.info(f"Server name from token: {server_name}")
            except Exception as e:
                app.logger.error(f"Error decoding token payload: {e}")
                return jsonify({"error": "Could not extract region from token. Please provide server_name parameter"}), 400
        
        # Normalize region
        if server_name in {"ID", "IDN", "INDONESIA"}:
            server_name = "ID"
            app.logger.info("Using Indonesia region (ID)")
        elif server_name in {"BR", "US", "SAC", "NA"}:
            pass  # Keep as is
        elif server_name in {"IND"}:
            pass  # Keep as is
        else:
            # Default to polar bear for unknown regions
            app.logger.info(f"Unknown region {server_name}, using default")
        
        if not server_name:
            return jsonify({"error": "server_name could not be determined"}), 400
        
        app.logger.info(f"Processing UID: {uid}, Region: {server_name}")
        app.logger.info(f"Total tokens available: {total_tokens}")
        
        # Encrypt UID
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption of UID failed."}), 500

        # Get before likes count
        before = make_request(encrypted_uid, server_name, token)
        if before is None:
            return jsonify({
                "error": "Failed to retrieve player info. Check tokens.json or network connection.",
                "region": server_name,
                "uid": uid
            }), 500
        
        try:
            data_before = json.loads(MessageToJson(before))
            before_like = int(data_before.get('AccountInfo', {}).get('Likes', 0) or 0)
            app.logger.info(f"Likes before: {before_like}")
        except Exception as e:
            app.logger.error(f"Error parsing before likes: {e}")
            return jsonify({"error": f"Error parsing player data: {str(e)}"}), 500

        # Get LikeProfile URL
        url = get_like_profile_url(server_name)
        app.logger.info(f"LikeProfile URL: {url}")

        # Send like requests (async) - menggunakan SEMUA token
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(send_multiple_requests(uid, server_name, url))
            loop.close()
            
            # Extract success count from result
            if isinstance(result, dict):
                success_count = result.get("success_count", 0)
                total_sent = result.get("total_requests", 0)
            else:
                success_count = 0
                total_sent = 0
                
            app.logger.info(f"Like requests completed. Success: {success_count}/{total_sent}")
            
        except Exception as e:
            app.logger.error(f"Error in async requests: {e}")
            return jsonify({"error": f"Error sending like requests: {str(e)}"}), 500

        # Get after likes count
        after = make_request(encrypted_uid, server_name, token)
        if after is None:
            return jsonify({"error": "Failed to retrieve player info after likes."}), 500
        
        try:
            data_after = json.loads(MessageToJson(after))
            account_info = data_after.get('AccountInfo', {})
            after_like = int(account_info.get('Likes', 0) or 0)
            player_uid = int(account_info.get('UID', 0) or 0)
            player_name = str(account_info.get('PlayerNickname', ''))
            
            like_given = after_like - before_like
            
            app.logger.info(f"Final result - UID: {player_uid}, Name: {player_name}, "
                          f"Likes before: {before_like}, Likes after: {after_like}, "
                          f"Likes given: {like_given}")
            
            return jsonify({
                "credit": "https://t.me/paglu_dev",
                "region": server_name,
                "total_tokens_used": total_tokens,
                "successful_requests": success_count if 'success_count' in locals() else 0,
                "LikesGivenByAPI": like_given,
                "LikesafterCommand": after_like,
                "LikesbeforeCommand": before_like,
                "PlayerNickname": player_name,
                "UID": player_uid,
                "status": 1 if like_given > 0 else 2,
                "message": f"Successfully sent {success_count if 'success_count' in locals() else 0} likes from {total_tokens} tokens" if like_given > 0 else "No likes were given"
            })
        except Exception as e:
            app.logger.error(f"Error parsing after likes: {e}")
            return jsonify({"error": f"Error parsing after data: {str(e)}"}), 500
            
    except Exception as e:
        app.logger.error(f"Unhandled error in handle_requests: {e}")
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=5000)