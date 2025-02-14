from typing import Dict, List, Any
import aiohttp
import asyncio

STAT_CATEGORIES = {
    'passingYards': 'Passing Yards',
    'rushingYards': 'Rushing Yards',
    'receivingYards': 'Receiving Yards',
    'sacks': 'Sacks',
    'interceptions': 'Interceptions',
    'passingTouchdowns': 'Passing TDs',
    'receptions': 'Receptions'
}

async def fetch_stats_leaders(year: str, no_of_players: int = 5) -> Dict[str, List[Dict[str, Any]]]:
    """
    Fetch NFL stats leaders for different categories.
    
    Args:
        year: Season year
        
    Returns:
        Dictionary with category names as keys and lists of player stats as values
    """
    url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/leaders"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            
            leaders: Dict[str, List[Dict[str, Any]]] = {}
            
            for category in data['categories']:
                if category['name'] not in STAT_CATEGORIES:
                    continue

                category_name = category['name']
                leaders[category_name] = []
                
                for i, leader in enumerate(category['leaders']):
                    if i >= no_of_players:
                        break
                    # Get athlete details
                    async with session.get(leader['athlete']['$ref']) as athlete_response:
                        athlete_data = await athlete_response.json()
                        
                        leader_info = {
                            'name': athlete_data['displayName'],
                            'position': athlete_data['position']['abbreviation'],
                            # 'team': athlete_data['team']['name'],
                            'value': leader['value'],
                            'rank': i + 1
                        }
                        leaders[category_name].append(leader_info)
            
            return leaders

async def main():
    leaders = await fetch_stats_leaders("2024")
    for category, players in leaders.items():
        print(f"\n{category}:")
        for player in players:
            print(f"{player['rank']}. {player['name']} - {player['value']}")

if __name__ == "__main__":
    asyncio.run(main())