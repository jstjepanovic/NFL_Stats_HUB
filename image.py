import aiohttp

async def fetch_logo_image(self, url):
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    return None
                image_data = await response.read()
                return image_data
    except Exception as e:
        print(f"Error fetching logo: {e}")
        return None