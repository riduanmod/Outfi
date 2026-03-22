import os
import base64
import game_version  # গেম ভার্সনের ফাইল ইম্পোর্ট করা হলো

class Config:
    # ডিফল্ট পোর্ট এবং সেটিংস
    PORT = int(os.environ.get("PORT", 5000))
    DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
    
    # ক্রিপ্টোগ্রাফি কি (Keys)
    MAIN_KEY = base64.b64decode(os.environ.get("MAIN_KEY", "WWcmdGMlREV1aDYlWmNeOA=="))
    MAIN_IV = base64.b64decode(os.environ.get("MAIN_IV", "Nm95WkRyMjJFM3ljaGpNJQ=="))
    
    # গেম কনফিগারেশন - game_version.py থেকে ডাটা নেওয়া হচ্ছে
    RELEASE_VERSION = game_version.RELEASE_VERSION
    UNITY_VERSION = game_version.UNITY_VERSION
    CLIENT_VERSION = game_version.CLIENT_VERSION
    
    # ডায়নামিক ইউজার এজেন্ট তৈরি করা হচ্ছে game_version.py এর ভ্যালু ব্যবহার করে
    USER_AGENT = f"Dalvik/2.1.0 (Linux; U; {game_version.ANDROID_OS_VERSION}; {game_version.USER_AGENT_MODEL} Build/RKQ1.211119.001)"
    
    # রিজিয়ন সেটিংস
    SUPPORTED_REGIONS = {"IND", "BR", "US", "SAC", "NA", "SG", "RU", "ID", "TW", "VN", "TH", "ME", "PK", "CIS", "BD", "EU"}
    
    # ক্রিডেনশিয়ালস (Credentials)
    ACCOUNTS = {
        "ME": "uid=3825052753&password=2D99628D3083D88F0997093B5D3E65F5ED13321941FB7B3FCDFB207E203832BE",
        "BD": "uid=4343645299&password=C5C216587364AD7247730F433CABA4A5C91C6889BCCC2A4D8105E3D7297B5CE2",
        "DEFAULT": "uid=3301239795&password=DD40EE772FCBD61409BB15033E3DE1B1C54EDA83B75DF0CDD24C34C7C8798475",
        "OTHER": "uid=3788023112&password=5356B7495AC2AD04C0A483CF234D6E56FB29080AC2461DD51E0544F8D455CC24"
    }

    @staticmethod
    def get_account(region):
        r = region.upper()
        if r == "ME": return Config.ACCOUNTS["ME"]
        if r == "BD": return Config.ACCOUNTS["BD"]
        if r in {"BR", "US", "SAC"}: return Config.ACCOUNTS["OTHER"]
        return Config.ACCOUNTS["DEFAULT"]
