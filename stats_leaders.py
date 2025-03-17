from typing import Dict, List, Any
import asyncio
import aiohttp
import time
from datetime import datetime

# Cache for storing fetched data
_cache = {}
_cache_expiry = {}
CACHE_DURATION = 300  # 5 minutes (in seconds)

# Stat categories mapping
STAT_CATEGORIES = {
    'passingYards': 'Passing Yards',
    'rushingYards': 'Rushing Yards',
    'receivingYards': 'Receiving Yards',
    'sacks': 'Sacks',
    'interceptions': 'Interceptions',
    'passingTouchdowns': 'Passing TDs',
    'receptions': 'Receptions'
}

async def fetch_stats_leaders(year: str | None = None, no_of_players: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch NFL stats leaders for different categories.
    
    Args:
        year: Season year. If None, uses current year minus 1.
        no_of_players: Number of top players to fetch per category
        
    Returns:
        Dictionary with category names as keys and lists of player stats as values
    """
    # If year is not provided, use current year minus 1 (same as standings.py)
    if year is None:
        year = str(datetime.now().year - 1)
        
    # Check cache first
    cache_key = f"leaders_{year}_{no_of_players}"
    current_time = time.time()
    
    # Return cached data if available and not expired
    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        print(f"Using cached stats leaders data for {year}")
        return _cache[cache_key]
    
    print(f"Fetching fresh stats leaders data for {year}")
    
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/leaders"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    print(f"Error: Received status code {response.status} from {url}")
                    return {}
                    
                data = await response.json()
                leaders: Dict[str, List[Dict[str, Any]]] = {}
                
                for category in data.get('categories', []):
                    category_name = category.get('name')
                    if category_name not in STAT_CATEGORIES:
                        continue
                    
                    display_name = STAT_CATEGORIES[category_name]
                    leaders[category_name] = []
                    
                    for i, leader in enumerate(category.get('leaders', [])):
                        if i >= no_of_players:
                            break
                            
                        try:
                            # Get athlete details
                            athlete_ref = leader.get('athlete', {}).get('$ref')
                            if not athlete_ref:
                                continue
                                
                            async with session.get(athlete_ref) as athlete_response:
                                if athlete_response.status != 200:
                                    print(f"Error fetching athlete data: {athlete_response.status}")
                                    continue
                                    
                                athlete_data = await athlete_response.json()
                                
                                # Get team data if available
                                team_name = "Free Agent"
                                team_abbr = "FA"
                                
                                if 'team' in athlete_data and '$ref' in athlete_data['team']:
                                    try:
                                        async with session.get(athlete_data['team']['$ref']) as team_response:
                                            if team_response.status == 200:
                                                team_data = await team_response.json()
                                                team_name = team_data.get('displayName', 'Unknown')
                                                team_abbr = team_data.get('abbreviation', 'UNK')
                                    except Exception as e:
                                        print(f"Error fetching team data: {e}")
                                
                                leader_info = {
                                    'name': athlete_data.get('displayName', 'Unknown'),
                                    'position': athlete_data.get('position', {}).get('abbreviation', 'UNK'),
                                    'team': team_name,
                                    'team_abbr': team_abbr,
                                    'value': leader.get('value', 0),
                                    'rank': i + 1,
                                    'athlete_id': athlete_data.get('id')
                                }
                                
                                leaders[category_name].append(leader_info)
                        except Exception as e:
                            print(f"Error processing leader data: {e}")
                            continue
                
                # Cache the result
                _cache[cache_key] = leaders
                _cache_expiry[cache_key] = current_time + CACHE_DURATION
                
                return leaders
    except aiohttp.ClientError as e:
        print(f"Connection error: {e}")
        return {}
    except asyncio.TimeoutError:
        print("Request timed out")
        return {}
    except Exception as e:
        print(f"Unexpected error in fetch_stats_leaders: {e}")
        # If cache exists but is expired, use it as fallback
        if cache_key in _cache:
            print("Using expired cache as fallback")
            return _cache[cache_key]
        return {}

async def fetch_player_stats(athlete_id: str, year: str | None = None) -> Dict[str, Any]:
    """
    Fetch detailed stats for a specific player.
    
    Args:
        athlete_id: The ESPN athlete ID
        year: Season year. If None, uses current year minus 1.
        
    Returns:
        Dictionary with player stats
    """
    # If year is not provided, use current year minus 1
    if year is None:
        year = str(datetime.now().year - 1)
        
    # Check cache first
    cache_key = f"player_stats_{athlete_id}_{year}"
    current_time = time.time()
    
    # Return cached data if available and not expired
    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        print(f"Using cached player stats for athlete {athlete_id}, year {year}")
        return _cache[cache_key]
    
    print(f"Fetching fresh player stats for athlete {athlete_id}, year {year}")
    
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/athletes/{athlete_id}/statistics"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    print(f"Error: Received status code {response.status} from {url}")
                    return {}
                    
                data = await response.json()
                
                # Process and structure the player stats
                player_stats = {
                    'athlete_id': athlete_id,
                    'stats': {},
                    'categories': {}
                }
                
                # Extract stats from the response
                if 'splits' in data and 'categories' in data['splits'][0]:
                    for category in data['splits'][0]['categories']:
                        category_name = category.get('name', 'unknown')
                        player_stats['categories'][category_name] = {}
                        
                        for stat in category.get('stats', []):
                            stat_name = stat.get('name', 'unknown')
                            stat_value = stat.get('value', 0)
                            player_stats['stats'][stat_name] = stat_value
                            player_stats['categories'][category_name][stat_name] = stat_value
                
                # Cache the result
                _cache[cache_key] = player_stats
                _cache_expiry[cache_key] = current_time + CACHE_DURATION
                
                return player_stats
    except Exception as e:
        print(f"Error fetching player stats: {e}")
        # If cache exists but is expired, use it as fallback
        if cache_key in _cache:
            print("Using expired cache as fallback")
            return _cache[cache_key]
        return {}

# For testing the module directly
if __name__ == "__main__":
    async def test():
        current_year = '2024'
        
        print(f"NFL Stats Leaders for {current_year}:")
        leaders = await fetch_stats_leaders(current_year)
        
        for category, players in leaders.items():
            print(f"\n{STAT_CATEGORIES[category]}:")
            for player in players:
                print(f"{player['rank']}. {player['name']} ({player['team_abbr']}) - {player['value']}")
        
        # Test player stats if leaders were found
        if leaders and 'passingYards' in leaders and leaders['passingYards']:
            top_qb_id = leaders['passingYards'][0]['athlete_id']
            print(f"\nDetailed stats for top QB (ID: {top_qb_id}):")
            player_stats = await fetch_player_stats(top_qb_id, current_year)
            
            # Display some key stats
            if player_stats and 'stats' in player_stats:
                stats = player_stats['stats']
                print(f"Passing yards: {stats.get('passingYards', 'N/A')}")
                print(f"Passing TDs: {stats.get('passingTouchdowns', 'N/A')}")
                print(f"Interceptions: {stats.get('interceptions', 'N/A')}")
                print(f"Completion %: {stats.get('completionPct', 'N/A')}")
    
    asyncio.run(test())
