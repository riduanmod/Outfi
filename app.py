import time
import json
import requests
import io
import os
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from cachetools import TTLCache
from collections import defaultdict
from google.protobuf import json_format, message
from google.protobuf.message import Message
from Crypto.Cipher import AES
from PIL import Image

# === Local Imports ===
from config import Config
import FreeFire_pb2
import main_pb2
import AccountPersonalShow_pb2

# === Flask App Setup ===
app = Flask(__name__)
CORS(app)
app.json.sort_keys = False 

cache = TTLCache(maxsize=100, ttl=300)
cached_tokens = defaultdict(dict)

# === Helper Functions ===
def pad(text: bytes) -> bytes:
    padding_length = AES.block_size - (len(text) % AES.block_size)
    return text + bytes([padding_length] * padding_length)

def aes_cbc_encrypt(key: bytes, iv: bytes, plaintext: bytes) -> bytes:
    aes = AES.new(key, AES.MODE_CBC, iv)
    return aes.encrypt(pad(plaintext))

def decode_protobuf(encoded_data: bytes, message_type: message.Message) -> message.Message:
    instance = message_type()
    instance.ParseFromString(encoded_data)
    return instance

def json_to_proto_sync(json_data: str, proto_message: Message) -> bytes:
    json_format.ParseDict(json.loads(json_data), proto_message)
    return proto_message.SerializeToString()

# === Token & Auth ===
def get_access_token(account: str):
    url = "https://ffmconnect.live.gop.garenanow.com/oauth/guest/token/grant"
    payload = account + "&response_type=token&client_type=2&client_secret=2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3&client_id=100067"
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Content-Type': "application/x-www-form-urlencoded"
    }
    resp = requests.post(url, data=payload, headers=headers)
    if resp.status_code != 200:
        raise Exception(f"Token Endpoint Failed. Status: {resp.status_code}, Response: {resp.text}")
    data = resp.json()
    return data.get("access_token", "0"), data.get("open_id", "0")

def create_jwt(region: str):
    account = Config.get_account(region)
    token_val, open_id = get_access_token(account)
    body = json.dumps({"open_id": open_id, "open_id_type": "4", "login_token": token_val, "orign_platform_type": "4"})
    proto_bytes = json_to_proto_sync(body, FreeFire_pb2.LoginReq())
    payload = aes_cbc_encrypt(Config.MAIN_KEY, Config.MAIN_IV, proto_bytes)
    url = "https://loginbp.ggblueshark.com/MajorLogin"
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Content-Type': "application/octet-stream", 
        'X-Unity-Version': Config.UNITY_VERSION, 
        'ReleaseVersion': Config.RELEASE_VERSION
    }
    resp = requests.post(url, data=payload, headers=headers)
    
    if resp.status_code != 200:
        raise Exception(f"MajorLogin HTTP Error {resp.status_code}: {resp.text}")

    try:
        msg = json.loads(json_format.MessageToJson(decode_protobuf(resp.content, FreeFire_pb2.LoginRes)))
    except Exception as e:
        # এটি সার্ভার থেকে আসা আসল এররটি ব্রাউজারে দেখাবে
        raise Exception(f"Garena Rejected Request. Server Response: {str(resp.content[:150])}")

    cached_tokens[region] = {
        'token': f"Bearer {msg.get('token','0')}",
        'region': msg.get('lockRegion','0'),
        'server_url': msg.get('serverUrl','0'),
        'expires_at': time.time() + 25200
    }

def get_token_info(region: str):
    info = cached_tokens.get(region)
    if info and time.time() < info['expires_at']:
        return info['token'], info['region'], info['server_url']
    create_jwt(region)
    info = cached_tokens[region]
    return info['token'], info['region'], info['server_url']

def GetAccountInformation(uid, unk, region, endpoint):
    payload = json_to_proto_sync(json.dumps({'a': int(uid), 'b': int(unk)}), main_pb2.GetPlayerPersonalShow())
    data_enc = aes_cbc_encrypt(Config.MAIN_KEY, Config.MAIN_IV, payload)
    token, lock, server = get_token_info(region)
    headers = {
        'User-Agent': Config.USER_AGENT, 
        'Content-Type': "application/octet-stream", 
        'Authorization': token, 
        'X-Unity-Version': Config.UNITY_VERSION, 
        'ReleaseVersion': Config.RELEASE_VERSION
    }
    resp = requests.post(server + endpoint, data=data_enc, headers=headers)
    
    if resp.status_code != 200:
        raise Exception(f"GetInfo HTTP Error {resp.status_code}: {resp.text}")

    try:
        return json.loads(json_format.MessageToJson(decode_protobuf(resp.content, AccountPersonalShow_pb2.AccountPersonalShowInfo)))
    except Exception as e:
        raise Exception(f"GetInfo Decode Error. Server Response: {str(resp.content[:150])}")

# === Image Generation Logic ===
def generate_outfit_image(items_list):
    try:
        bg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outfit.png")
        bg = Image.open(bg_path).convert("RGBA")
        
        positions = [
            (200, 20), (350, 80), (400, 250), (350, 400), 
            (200, 450), (50, 400), (0, 250), (50, 80)
        ]
        icon_size = (100, 100) 

        for idx, item_id in enumerate(items_list[:8]): 
            item_url = f"https://dl.dir.freefiremobile.com/mna/HD/{item_id}.png"
            try:
                img_resp = requests.get(item_url, timeout=3)
                if img_resp.status_code == 200:
                    item_img = Image.open(io.BytesIO(img_resp.content)).convert("RGBA")
                    item_img = item_img.resize(icon_size)
                    bg.paste(item_img, positions[idx], item_img)
            except Exception as e:
                print(f"Error loading item {item_id}: {e}")

        img_io = io.BytesIO()
        bg.save(img_io, 'PNG')
        img_io.seek(0)
        return img_io

    except Exception as e:
        print("Image Generation Error:", e)
        return None

# === API Routes ===
@app.route('/get')
def get_account_info():
    uid = request.args.get('uid')
    output_type = request.args.get('type', 'image') 
    
    if not uid:
        return jsonify({"error": "Please provide UID."}), 400
    
    try:
        region = "ME"
        data = GetAccountInformation(uid, 7, region, "/GetPlayerPersonalShow")
        
        profile_info = data.get("profileInfo", {})
        weapon_info = data.get("basicInfo", {}).get("weaponSkinShows", [])
        clothes_info = profile_info.get("clothes", [])
        
        all_items = clothes_info + weapon_info 
        
        if output_type == 'json':
            return jsonify({
                "uid": uid,
                "equipped_items": all_items
            }), 200
        
        img_io = generate_outfit_image(all_items)
        if img_io:
            return send_file(img_io, mimetype='image/png')
        else:
            return jsonify({"error": "Failed to generate image."}), 500
            
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
