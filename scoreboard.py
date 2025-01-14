from typing import Dict, List, Any
import asyncio
import aiohttp

async def fetch_standings(url: str, conference_name: str) -> List[Dict[str, Any]]:
    """
    Fetch NFL standings data for a conference.
    
    Args:
        url: API endpoint URL
        conference_name: Name of the conference (AFC/NFC)
        
    Returns:
        List of team standings information
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data: Dict[str, Any] = await response.json()
            
            standings: List[Dict[str, Any]] = []
            for entry in data['standings']:
                team: Dict[str, Any] = entry['team']
                stats: List[Dict[str, Any]] = entry['records'][0]['stats']
                
                async with session.get(team['$ref']) as team_response:
                    team_data: Dict[str, Any] = await team_response.json()

                async with session.get(team_data['groups']['$ref']) as group_response:
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
                
            return standings

async def update_standings(year: str) -> Dict[str, List[Dict[str, Any]]]:
    nfc_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/groups/7/standings/0?lang=en&region=us"
    afc_url = f"https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/2/groups/8/standings/0?lang=en&region=us"
    
    nfc_standings, afc_standings = await asyncio.gather(
        fetch_standings(nfc_url, "NFC"),
        fetch_standings(afc_url, "AFC")
    )
    
    all_standings = nfc_standings + afc_standings
    divisions = {}
    
    for team in all_standings:
        key = f"{team['division']}"
        if key not in divisions:
            divisions[key] = []
        divisions[key].append(team)
    
    return divisions

def sort_teams(teams):
    return sorted(teams, key=lambda x: (-x['wins'], -x['winPercent']))