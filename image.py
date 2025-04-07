import aiohttp

async def fetch_logo_image(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
        return None
    except Exception as e:
        print(f"Error fetching logo: {e}")
        return None