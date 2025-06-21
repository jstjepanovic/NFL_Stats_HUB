import unittest
import types

from app import validate_data


class DummyApp:
    def __init__(self):
        self.root = types.SimpleNamespace()
        self.root.after = lambda delay, func: func()
        self.stats_notebook = types.SimpleNamespace()
        self.stats_notebook.index = lambda x=None: 0
        self.current_player_stats = {
            "passingYards": [
                {
                    "name": "A","position": "QB", "team": "X",
                    "team_abbr": "XA", "value": 100, "rank": 1
                }
            ]
        }
        self.current_standings = {
            "AFC North": [
                {
                    "conference": "AFC", "division": "AFC North",
                    "name": "Team1", "abbreviation": "T1", "wins": 10,
                    "losses": 2, "ties": 0, "winPercent": 0.833
                }
            ]
        }

class TestValidation(unittest.TestCase):
    def test_validate_player_stats(self):
        app = DummyApp()
        @validate_data
        async def dummy_export(self):
            return True
        
        import asyncio
        async def run_test():
            return await dummy_export(app)
        result = asyncio.run(run_test())
        self.assertTrue(result)

    def test_validate_player_stats_missing(self):
        app = DummyApp()
        app.current_player_stats = {}
        async def dummy_export(self):
            return True
        dummy_export.__name__ = 'export_player_stats_to_csv' 
        decorated = validate_data(dummy_export)
        import asyncio
        async def run_test():
            return await decorated(app)
        result = asyncio.run(run_test())
        self.assertIsNone(result)

    def test_validate_standings(self):
        app = DummyApp()
        @validate_data
        async def dummy_export(self):
            return True
        import asyncio
        app.stats_notebook = types.SimpleNamespace()
        async def run_test():
            return await dummy_export(app)
        result = asyncio.run(run_test())
        self.assertTrue(result)

if __name__ == "__main__":
    unittest.main()
