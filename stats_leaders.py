import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp


_cache = {}
_cache_expiry = {}
CACHE_DURATION = 600

STAT_CATEGORIES = {
    'passingYards': 'Passing Yards',
    'rushingYards': 'Rushing Yards',
    'receivingYards': 'Receiving Yards',
    'sacks': 'Sacks',
    'interceptions': 'Interceptions',
    'passingTouchdowns': 'Passing TDs',
    'receptions': 'Receptions'
}


async def fetch_stats_leaders(
    year: Optional[str] = None,
    category: Optional[str] = None,
    no_of_players: int = 20
) -> Dict[str, List[Dict[str, Any]]]:
    if year is None:
        year = str(datetime.now().year - 1)

    if category is None or category not in STAT_CATEGORIES:
        return {}

    cache_key = f"leaders_{year}_{category}_{no_of_players}"
    current_time = time.time()

    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        logging.info(
            f"Using cached stats leaders data for {category} in {year}"
        )
        return {category: _cache[cache_key]}

    logging.info(
        f"Fetching fresh stats leaders data for {category} in {year}"
    )

    url = (
        f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
        f"seasons/{year}/types/2/leaders?category={category}"
    )

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    logging.error(
                        f"Error: Received status code {response.status} "
                        f"from {url}"
                    )
                    return {}

                data = await response.json()
                leaders = await _parse_leaders_data(
                    session, data, category, no_of_players
                )

                _cache[cache_key] = leaders
                _cache_expiry[cache_key] = (
                    current_time + CACHE_DURATION
                )

                return {category: leaders}
    except Exception as e:
        logging.error(
            f"Unexpected error in fetch_stats_leaders: {e}"
        )
        if cache_key in _cache:
            logging.warning("Using expired cache as fallback")
            return {category: _cache[cache_key]}
        return {}

async def _parse_leaders_data(
    session: aiohttp.ClientSession,
    data: Dict[str, Any],
    category: str,
    no_of_players: int
) -> List[Dict[str, Any]]:
    leaders = []
    for cat in data.get('categories', []):
        if cat.get('name') == category:
            for i, leader in enumerate(cat.get('leaders', [])):
                if i >= no_of_players:
                    break
                leader_info = await _process_leader(
                    session, leader, category, i
                )
                if leader_info:
                    leaders.append(leader_info)
            break
    return leaders

async def _process_leader(
    session: aiohttp.ClientSession,
    leader: Dict[str, Any],
    category: str,
    index: int
) -> Optional[Dict[str, Any]]:
    athlete = leader.get('athlete', {})
    athlete_ref = athlete.get('$ref')
    if not athlete_ref:
        return None

    try:
        athlete_data = await fetch_json(session, athlete_ref)
    except Exception as e:
        logging.error(f"Error fetching athlete data: {e}")
        return None

    if not athlete_data:
        return None

    try:
        team_name, team_abbr = await get_team_info(session, athlete_data)
    except Exception as e:
        logging.error(f"Error fetching team info: {e}")
        team_name, team_abbr = "Unknown", "UNK"

    try:
        college = await get_college_info(session, athlete_data)
    except Exception as e:
        logging.error(f"Error fetching college info: {e}")
        college = None

    formatted_dob = None
    try:
        formatted_dob = format_date_of_birth(athlete_data.get('dateOfBirth'))
    except Exception as e:
        logging.error(f"Error formatting date: {e}")

    debut_year = (
        athlete_data.get('debutYear') or
        athlete_data.get('draft', {}).get('year')
    )
    draft_display = athlete_data.get('draft', {}).get('displayText')

    leader_info = {
        'name': athlete_data.get('displayName', 'Unknown'),
        'position': athlete_data.get('position', {}).get('abbreviation', 'UNK'),
        'team': team_name,
        'team_abbr': team_abbr,
        'category': category,
        'value': leader.get('value', 0),
        'rank': index + 1,
        'headshot': athlete_data.get('headshot', {}).get('href', None),
        'athlete_id': athlete_data.get('id'),
        'date_of_birth': formatted_dob,
        'debut_year': debut_year,
        'college': college,
        'draft': draft_display,
    }
    return leader_info

async def fetch_json(
    session: aiohttp.ClientSession, url: str
) -> Optional[Dict[str, Any]]:
    try:
        async with session.get(url) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        logging.error(f"Error fetching JSON from {url}: {e}")
    return None

async def get_team_info(
    session: aiohttp.ClientSession, athlete_data: Dict[str, Any]
) -> Tuple[str, str]:
    team_name = "Free Agent"
    team_abbr = "FA"
    team_ref = athlete_data.get('team', {}).get('$ref')
    if team_ref:
        team_data = await fetch_json(session, team_ref)
        if team_data:
            team_name = team_data.get('displayName', 'Unknown')
            team_abbr = team_data.get('abbreviation', 'UNK')
    return team_name, team_abbr

async def get_college_info(
    session: aiohttp.ClientSession, athlete_data: Dict[str, Any]
) -> Optional[str]:
    college_url = athlete_data.get('college', {}).get('$ref')
    if college_url:
        college_data = await fetch_json(session, college_url)
        if college_data:
            return college_data.get('name', 'Unknown')
    return None

def format_date_of_birth(dob: Optional[str]) -> Optional[str]:
    if dob:
        try:
            dob_date = datetime.strptime(dob, '%Y-%m-%dT%H:%M%z')
            return dob_date.strftime('%d.%m.%Y.')
        except Exception as e:
            logging.error(f"Error formatting date: {e}")
    return None


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    async def test():
        current_year = '2024'

        logging.info(
            f"NFL Stats Leaders for {current_year}:"
        )
        leaders = await fetch_stats_leaders(
            current_year, 'passingYards', 1
        )

        for category, players in leaders.items():
            logging.info(f"\n{STAT_CATEGORIES[category]}:")
            for player in players:
                logging.info(player)
                logging.info(
                    f"{player['rank']}. {player['name']} "
                    f"({player['team_abbr']}) - {player['value']}"
                )

    asyncio.run(test())
