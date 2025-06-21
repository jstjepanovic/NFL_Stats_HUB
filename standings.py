from typing import Any, Dict, List
import asyncio
import time
from datetime import datetime
import logging

import aiohttp


_cache = {}
_cache_expiry = {}
CACHE_DURATION = 600


async def fetch_standings(
    url: str, conference_name: str
) -> List[Dict[str, Any]]:
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    logging.error(
                        f"Error: Received status code {response.status} "
                        f"from {url}"
                    )
                    return []

                data: Dict[str, Any] = await response.json()
                standings: List[Dict[str, Any]] = []

                for entry in data['standings']:
                    team: Dict[str, Any] = entry['team']
                    stats: List[Dict[str, Any]] = entry['records'][0]['stats']

                    try:
                        async with session.get(team['$ref']) as team_response:
                            if team_response.status != 200:
                                logging.error(
                                    f"Error fetching team data: "
                                    f"{team_response.status}"
                                )
                                continue

                            team_data: Dict[str, Any] = (
                                await team_response.json()
                            )

                            async with session.get(
                                team_data['groups']['$ref']
                            ) as group_response:
                                if group_response.status != 200:
                                    logging.error(
                                        f"Error fetching group data: "
                                        f"{group_response.status}"
                                    )
                                    continue

                                group_data: Dict[str, Any] = (
                                    await group_response.json()
                                )
                                division: str = group_data['name']

                                team_info: Dict[str, Any] = {
                                    'conference': conference_name,
                                    'division': division,
                                    'name': team_data['displayName'],
                                    'abbreviation': team_data['abbreviation'],
                                    'wins': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'wins')
                                    ),
                                    'losses': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'losses')
                                    ),
                                    'ties': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'ties')
                                    ),
                                    'winPercent': float(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'winPercent')
                                    ),
                                    'logo': (
                                        team_data['logos'][0]['href']
                                        if team_data['logos'] else None
                                    ),
                                    'pointsFor': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'pointsFor')
                                    ),
                                    'pointsAgainst': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'pointsAgainst')
                                    ),
                                    'pointDifferential': int(next(
                                        stat['value'] for stat in stats
                                        if stat['name'] == 'pointDifferential')
                                    ),
                                    'homeRecord': 
                                        entry['records'][1]['summary'],
                                    'awayRecord':
                                        entry['records'][2]['summary'],
                                    'venue': (
                                        team_data['venue']['fullName']
                                        if team_data['venue'] else None
                                    ),
                                    'address': (
                                        team_data['venue']['address']
                                        if team_data['venue']['address']
                                        else None
                                    ),
                                    'team_id': team_data['id'],
                                }

                                standings.append(team_info)
                    except Exception as e:
                        logging.error(
                            f"Error processing team data: {e}"
                        )
                        continue

                return standings
    except aiohttp.ClientError as e:
        logging.error(f"Connection error: {e}")
        return []
    except asyncio.TimeoutError:
        logging.error("Request timed out")
        return []
    except Exception as e:
        logging.error(f"Unexpected error in fetch_standings: {e}")
        return []


async def update_standings(
    year: str | None = None
) -> Dict[str, List[Dict[str, Any]]]:
    if year is None:
        year = str(datetime.now().year - 1)

    cache_key = f"standings_{year}"
    current_time = time.time()

    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        logging.info(
            f"Using cached standings data for {year}"
        )
        return _cache[cache_key]

    logging.info(
        f"Fetching fresh standings data for {year}"
    )

    nfc_url = (
        f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
        f"seasons/{year}/types/2/groups/7/standings/0?lang=en&region=us"
    )
    afc_url = (
        f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
        f"seasons/{year}/types/2/groups/8/standings/0?lang=en&region=us"
    )

    try:
        nfc_standings, afc_standings = await asyncio.gather(
            fetch_standings(nfc_url, "NFC"),
            fetch_standings(afc_url, "AFC")
        )
    except Exception as e:
        logging.error(f"Error in update_standings: {e}")
        if cache_key in _cache:
            logging.warning("Using expired cache as fallback")
            return _cache[cache_key]
        return {}

    all_standings = nfc_standings + afc_standings

    divisions = {}
    for team in all_standings:
        key = f"{team['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(team)

    for division in divisions:
        divisions[division] = sort_teams(divisions[division])

    _cache[cache_key] = divisions
    _cache_expiry[cache_key] = current_time + CACHE_DURATION

    return divisions

def sort_teams(teams):
    return sorted(teams, key=lambda x: (-x['wins'], -x['winPercent']))


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    async def test():
        current_year = '2024'
        standings = await update_standings(current_year)

        logging.info(f"NFL Standings for {current_year}:")
        for division, teams in standings.items():
            logging.info(f"\n{division}:")
            for i, team in enumerate(teams, 1):
                logging.info(team)

    asyncio.run(test())
