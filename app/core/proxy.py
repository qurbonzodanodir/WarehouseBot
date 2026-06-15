import asyncio
import logging
import aiohttp
from aiohttp_socks import ProxyConnector

logger = logging.getLogger(__name__)

# Public lists of SOCKS5 and HTTP proxies updated frequently
PROXY_LIST_SOURCES = [
    ("socks5", "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt"),
    ("http", "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/http.txt"),
    ("socks5", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt"),
    ("http", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt"),
]

async def fetch_proxies_from_source(session: aiohttp.ClientSession, proxy_type: str, url: str) -> list[str]:
    """Fetch proxy list from a URL and format as proxy URLs."""
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                text = await response.text()
                proxies = []
                for line in text.strip().split("\n"):
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Format: ip:port
                        proxies.append(f"{proxy_type}://{line}")
                return proxies
    except Exception as e:
        logger.warning(f"Failed to fetch proxy list from {url}: {e}")
    return []

async def test_single_proxy(proxy_url: str) -> str | None:
    """Test a single proxy against api.telegram.org."""
    connector = ProxyConnector.from_url(proxy_url)
    try:
        async with aiohttp.ClientSession(connector=connector) as session:
            # Short timeout of 3 seconds to find responsive proxies quickly
            async with session.get("https://api.telegram.org", timeout=3) as response:
                # Any response status (even 404) means we successfully connected to Telegram
                if response.status in (200, 404):
                    return proxy_url
    except Exception:
        pass
    return None

async def get_working_proxy() -> str | None:
    """Collect public proxies and find the first working one."""
    logger.info("Starting proxy search...")
    async with aiohttp.ClientSession() as session:
        # Fetch proxy lists in parallel
        tasks = [fetch_proxies_from_source(session, ptype, url) for ptype, url in PROXY_LIST_SOURCES]
        results = await asyncio.gather(*tasks)
        
        # Flatten the list of proxy URLs
        all_proxies = []
        for res in results:
            all_proxies.extend(res)
            
        # Remove duplicates
        all_proxies = list(dict.fromkeys(all_proxies))
        logger.info(f"Fetched {len(all_proxies)} unique proxies. Testing for connectivity...")
        
        # Limit to the first 500 to avoid resource depletion
        proxies_to_test = all_proxies[:500]
        
        # Test proxies in batches of 50
        batch_size = 50
        for i in range(0, len(proxies_to_test), batch_size):
            batch = proxies_to_test[i:i+batch_size]
            test_tasks = [test_single_proxy(p) for p in batch]
            test_results = await asyncio.gather(*test_tasks)
            
            # Return the first working proxy found in this batch
            for result in test_results:
                if result:
                    logger.info(f"Found working proxy: {result}")
                    return result
                    
    logger.warning("No working proxies found.")
    return None

if __name__ == "__main__":
    # Quick self-test
    logging.basicConfig(level=logging.INFO)
    proxy = asyncio.run(get_working_proxy())
    print(f"Result: {proxy}")
