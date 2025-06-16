import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

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
                leaders = []

                for cat in data.get('categories', []):
                    if cat.get('name') == category:
                        for i, leader in enumerate(cat.get('leaders', [])):
                            if i >= no_of_players:
                                break

                            try:
                                athlete_ref = leader.get('athlete', {}).get('$ref')
                                if not athlete_ref:
                                    continue

                                async with session.get(athlete_ref) as athlete_response:
                                    if athlete_response.status != 200:
                                        continue

                                    athlete_data = await athlete_response.json()

                                    team_name = "Free Agent"
                                    team_abbr = "FA"

                                    if (
                                        'team' in athlete_data and
                                        '$ref' in athlete_data['team']
                                    ):
                                        try:
                                            async with session.get(
                                                athlete_data['team']['$ref']
                                            ) as team_response:
                                                if team_response.status == 200:
                                                    team_data = (
                                                        await team_response.json()
                                                    )
                                                    team_name = team_data.get(
                                                        'displayName', 'Unknown'
                                                    )
                                                    team_abbr = team_data.get(
                                                        'abbreviation', 'UNK'
                                                    )
                                        except Exception as e:
                                            logging.error(
                                                f"Error fetching team data: {e}"
                                            )

                                    college = None
                                    college_url = athlete_data.get(
                                        'college', {}
                                    ).get('$ref', None)

                                    if college_url:
                                        try:
                                            async with session.get(
                                                college_url
                                            ) as college_response:
                                                if college_response.status == 200:
                                                    college_data = (
                                                        await college_response.json()
                                                    )
                                                    college = college_data.get(
                                                        'name', 'Unknown'
                                                    )
                                        except Exception as e:
                                            logging.error(
                                                f"""Error fetching
                                                college data: {e}"""
                                            )

                                    dob = athlete_data.get('dateOfBirth', None)
                                    formatted_dob = None
                                    if dob:
                                        try:
                                            dob_date = datetime.strptime(
                                                dob, '%Y-%m-%dT%H:%M%z'
                                            )
                                            formatted_dob = dob_date.strftime(
                                                '%d.%m.%Y.'
                                            )
                                        except Exception as e:
                                            logging.error(
                                                f"Error formatting date: {e}"
                                            )

                                    debut_year = athlete_data.get(
                                        'debutYear', None
                                    )
                                    if not debut_year:
                                        debut_year = athlete_data.get(
                                            'draft', None
                                        ).get('year', None)

                                    draft = athlete_data.get('draft', {})
                                    draft_display = None
                                    if draft and isinstance(draft, dict):
                                        draft_display = draft.get(
                                            'displayText', None
                                        )

                                    leader_info = {
                                        'name': athlete_data.get(
                                            'displayName', 'Unknown'
                                        ),
                                        'position': athlete_data.get(
                                            'position', {}
                                        ).get('abbreviation', 'UNK'),
                                        'team': team_name,
                                        'team_abbr': team_abbr,
                                        'category': category,
                                        'value': leader.get('value', 0),
                                        'rank': i + 1,
                                        'headshot': athlete_data.get(
                                            'headshot', {}
                                        ).get('href', None),
                                        'athlete_id': athlete_data.get('id'),
                                        'date_of_birth': formatted_dob,
                                        'debut_year': athlete_data.get(
                                            'debutYear', None
                                        ),
                                        'college': college,
                                        'draft': draft_display,
                                    }

                                    leaders.append(leader_info)
                            except Exception as e:
                                logging.error(
                                    f"Error processing leader data: {e}"
                                )
                                continue

                        break

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
