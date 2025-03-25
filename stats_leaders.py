from typing import Dict, List, Any
import asyncio
import aiohttp
import time
from datetime import datetime

_cache = {}
_cache_expiry = {}
CACHE_DURATION = 600

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

async def fetch_stats_leaders(
        year: str | None = None,
        category: str | None = None,
        no_of_players: int = 20
    ) -> Dict[str, List[Dict[str, Any]]]:

    if year is None:
        year = str(datetime.now().year - 1)
    
    # If category is not provided, return empty dict
    if category is None or category not in STAT_CATEGORIES:
        return {}
    
    # Check cache first
    cache_key = f"leaders_{year}_{category}_{no_of_players}"
    current_time = time.time()
    
    # Return cached data if available and not expired
    if cache_key in _cache and _cache_expiry.get(cache_key, 0) > current_time:
        print(f"Using cached stats leaders data for {category} in {year}")
        return {category: _cache[cache_key]}
    
    print(f"Fetching fresh stats leaders data for {category} in {year}")
    
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/leaders?category={category}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=timeout) as response:
                if response.status != 200:
                    print(f"Error: Received status code {response.status} from {url}")
                    return {}
                
                data = await response.json()
                leaders = []
                
                # Find the specific category in the response
                for cat in data.get('categories', []):
                    if cat.get('name') == category:
                        # Process leaders for this category
                        for i, leader in enumerate(cat.get('leaders', [])):
                            if i >= no_of_players:
                                break
                            
                            try:
                                # Get athlete details
                                athlete_ref = leader.get('athlete', {}).get('$ref')
                                if not athlete_ref:
                                    continue
                                
                                async with session.get(athlete_ref) as athlete_response:
                                    if athlete_response.status != 200:
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
                                    
                                    leaders.append(leader_info)
                            except Exception as e:
                                print(f"Error processing leader data: {e}")
                                continue
                        
                        break
                
                # Cache the result
                _cache[cache_key] = leaders
                _cache_expiry[cache_key] = current_time + CACHE_DURATION
                
                return {category: leaders}
    except Exception as e:
        print(f"Unexpected error in fetch_stats_leaders: {e}")
        # If cache exists but is expired, use it as fallback
        if cache_key in _cache:
            print("Using expired cache as fallback")
            return {category: _cache[cache_key]}
        return {}

# For testing the module directly
if __name__ == "__main__":
    async def test():
        current_year = '2024'
        
        print(f"NFL Stats Leaders for {current_year}:")
        leaders = await fetch_stats_leaders(current_year, 'passingYards', 1)
        
        for category, players in leaders.items():
            print(f"\n{STAT_CATEGORIES[category]}:")
            for player in players:
                print(player)
                print(f"{player['rank']}. {player['name']} ({player['team_abbr']}) - {player['value']}")
    
    asyncio.run(test())
