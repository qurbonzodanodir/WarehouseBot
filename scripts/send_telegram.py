import asyncio
import os
import sys
from decimal import Decimal
import aiohttp
from aiohttp_socks import ProxyConnector

# Add project root to sys.path to enable app.core imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.core.proxy import get_working_proxy

async def upload_document(session: aiohttp.ClientSession, token: str, chat_id: str, file_path: str, caption: str) -> bool:
    """Send document to Telegram via the provided session."""
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    data = aiohttp.FormData()
    data.add_field("chat_id", chat_id)
    data.add_field("caption", caption)
    
    file_name = os.path.basename(file_path)
    data.add_field("document", open(file_path, "rb"), filename=file_name)
    
    try:
        async with session.post(url, data=data, timeout=300) as response:
            if response.status == 200:
                resp_json = await response.json()
                if resp_json.get("ok"):
                    print("Backup successfully sent to Telegram!")
                    return True
                else:
                    print(f"Telegram returned error: {resp_json}")
            else:
                resp_text = await response.text()
                print(f"Telegram returned HTTP {response.status}: {resp_text}")
    except Exception as e:
        print(f"Upload request failed: {e}")
    return False

async def main():
    if len(sys.argv) < 3:
        print("Usage: python send_telegram.py <file_path> <caption>")
        sys.exit(1)
        
    file_path = sys.argv[1]
    caption = sys.argv[2]
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        sys.exit(1)
        
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("BACKUP_CHAT_ID") or os.getenv("OWNER_TELEGRAM_ID")
    
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN environment variable is not set.")
        sys.exit(1)
    if not chat_id:
        print("Error: BACKUP_CHAT_ID or OWNER_TELEGRAM_ID environment variable is not set.")
        sys.exit(1)
        
    print(f"Attempting to upload {file_path} to chat {chat_id}...")
    
    # 1. Try sending directly first (fast path)
    print("Trying direct connection...")
    async with aiohttp.ClientSession() as session:
        success = await upload_document(session, token, chat_id, file_path, caption)
        if success:
            sys.exit(0)
            
    # 2. Direct upload failed, try finding a working proxy
    print("Direct connection failed. Searching for a working proxy...")
    proxy_url = await get_working_proxy()
    if not proxy_url:
        print("Error: Direct connection failed and no working proxy was found.")
        sys.exit(1)
        
    print(f"Attempting upload via proxy: {proxy_url}")
    connector = ProxyConnector.from_url(proxy_url)
    async with aiohttp.ClientSession(connector=connector) as session:
        success = await upload_document(session, token, chat_id, file_path, caption)
        if success:
            sys.exit(0)
        else:
            print("Error: Upload failed even when using proxy.")
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
