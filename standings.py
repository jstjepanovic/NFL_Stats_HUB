from typing import Dict, List, Any
import asyncio
import aiohttp
import time
from datetime import datetime

_cache = {}
_cache_expiry = {}
CACHE_DURATION = 600

async def fetch_standings(url: str, conference_name: str) -> List[Dict[str, Any]]:
    """
    Fetch NFL standings data for a conference.
    
    Args:
        url: API endpoint URL
        conference_name: Name of the conference (AFC/NFC)
        
    Returns:
        List of team standings information
    """
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    print(f"Error: Received status code {response.status} from {url}")
                    return []
                    
                data: Dict[str, Any] = await response.json()
                standings: List[Dict[str, Any]] = []
                
                for entry in data['standings']:
                    team: Dict[str, Any] = entry['team']
                    stats: List[Dict[str, Any]] = entry['records'][0]['stats']
                    
                    try:
                        async with session.get(team['$ref']) as team_response:
                            if team_response.status != 200:
                                print(f"Error fetching team data: {team_response.status}")
                                continue
                                
                            team_data: Dict[str, Any] = await team_response.json()
                            
                            async with session.get(team_data['groups']['$ref']) as group_response:
                                if group_response.status != 200:
                                    print(f"Error fetching group data: {group_response.status}")
                                    continue
                                    
                                group_data: Dict[str, Any] = await group_response.json()
                                division: str = group_data['name']
                                
                                team_info: Dict[str, Any] = {
                                    'conference': conference_name,
                                    'division': division,
                                    'name': team_data['displayName'],
                                    'abbreviation': team_data['abbreviation'],
                                    'wins': int(next(stat['value'] for stat in stats if stat['name'] == 'wins')),
                                    'losses': int(next(stat['value'] for stat in stats if stat['name'] == 'losses')),
                                    'ties': int(next(stat['value'] for stat in stats if stat['name'] == 'ties')),
                                    'winPercent': float(next(stat['value'] for stat in stats 
                                                            if stat['name'] == 'winPercent')),
                                }
                                
                                standings.append(team_info)
                    except Exception as e:
                        print(f"Error processing team data: {e}")
                        continue
                        
                return standings
    except aiohttp.ClientError as e:
        print(f"Connection error: {e}")
        return []
    except asyncio.TimeoutError:
        print("Request timed out")
        return []
    except Exception as e:
        print(f"Unexpected error in fetch_standings: {e}")
        return []

async def update_standings(year: str | None = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Update NFL standings for the specified year.
    
    Args:
        year: The year to fetch standings for. If None, uses current year.
        
    Returns:
        Dictionary of divisions with their teams
    """
    # If year is not provided, use current year
    if year is None:
        year = str(datetime.now().year - 1)
        
    # Check cache first
    cache_key = f"standings_{year}"
    current_time = time.time()
    
    # Return cached data if available and not expired
    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        print(f"Using cached standings data for {year}")
        return _cache[cache_key]
    
    print(f"Fetching fresh standings data for {year}")
    
    # URLs for NFC and AFC standings
    nfc_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/groups/7/standings/0?lang=en&region=us"
    afc_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/groups/8/standings/0?lang=en&region=us"
    
    try:
        # Fetch both conferences in parallel
        nfc_standings, afc_standings = await asyncio.gather(
            fetch_standings(nfc_url, "NFC"),
            fetch_standings(afc_url, "AFC")
        )
        
        # Combine standings
        all_standings = nfc_standings + afc_standings
        
        # Group by division
        divisions = {}
        for team in all_standings:
            key = f"{team['division']}"
            if key not in divisions:
                divisions[key] = []
            divisions[key].append(team)
        
        # Sort teams within each division
        for division in divisions:
            divisions[division] = sort_teams(divisions[division])
        
        # Cache the result
        _cache[cache_key] = divisions
        _cache_expiry[cache_key] = current_time + CACHE_DURATION
        
        return divisions
    except Exception as e:
        print(f"Error in update_standings: {e}")
        if cache_key in _cache:
            print("Using expired cache as fallback")
            return _cache[cache_key]
        return {}

def sort_teams(teams):
    """
    Sort teams by wins and win percentage.
    
    Args:
        teams: List of team dictionaries
        
    Returns:
        Sorted list of teams
    """
    return sorted(teams, key=lambda x: (-x['wins'], -x['winPercent']))


if __name__ == "__main__":
    async def test():
        current_year = '2024'
        standings = await update_standings(current_year)
        
        print(f"NFL Standings for {current_year}:")
        for division, teams in standings.items():
            print(f"\n{division}:")
            for i, team in enumerate(teams, 1):
                print(f"{i}. {team['abbreviation']} {team['name']}: {team['wins']}-{team['losses']}-{team['ties']} ({team['winPercent']:.3f})")
    
    asyncio.run(test())
