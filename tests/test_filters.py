# Standard library imports
import unittest
from typing import List, Dict, Any

# Local application imports
from app import create_filter

def sample_players():
    return [
        {"name": "A", "position": "QB", "team": "X", "team_abbr": "XA", "value": 100, "rank": 1},
        {"name": "B", "position": "RB", "team": "Y", "team_abbr": "YA", "value": 200, "rank": 2},
    ]

def sample_standings():
    return {
        "AFC North": [
            {
                "conference": "AFC", "division": "AFC North", "name": "Team1",
                "abbreviation": "T1", "wins": 10, "losses": 2, "ties": 0,
                "winPercent": 0.833
            },
            {
                "conference": "AFC", "division": "AFC North", "name": "Team2",
                "abbreviation": "T2", "wins": 8, "losses": 4, "ties": 0,
                "winPercent": 0.667
            },
        ]
    }

class TestFilters(unittest.TestCase):
    def test_team_filter(self):
        players = sample_players()
        team_filter = create_filter(lambda p: p["team_abbr"] == "XA")
        filtered = team_filter(players)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "A")

    def test_min_wins_filter(self):
        standings = sample_standings()
        teams = standings["AFC North"]
        win_filter = create_filter(lambda t: t["wins"] >= 9)
        filtered = win_filter(teams)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["name"], "Team1")

if __name__ == "__main__":
    unittest.main()
