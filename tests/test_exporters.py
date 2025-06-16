# Standard library imports
import unittest
import tempfile
import os
import json
import csv
import openpyxl
from typing import Any, Dict, List

# Local application imports
from exporters import CSVDataExporter, JSONDataExporter, ExcelDataExporter

class TestExporters(unittest.TestCase):
    def setUp(self):
        self.sample_data = [
            {
                "name": "Player 1", "position": "QB", "team": "TeamA",
                "team_abbr": "TA", "value": 1234, "rank": 1
            },
            {
                "name": "Player 2", "position": "RB", "team": "TeamB",
                "team_abbr": "TB", "value": 567, "rank": 2
            }
        ]
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_csv_exporter(self):
        filename = os.path.join(self.tempdir.name, "test.csv")
        exporter = CSVDataExporter()
        
        import asyncio
        asyncio.run(exporter.save(self.sample_data, filename))
        with open(filename, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        self.assertEqual(rows[0], list(self.sample_data[0].keys()))
        self.assertEqual(rows[1][0], "Player 1")
        self.assertEqual(rows[2][0], "Player 2")

    def test_json_exporter(self):
        filename = os.path.join(self.tempdir.name, "test.json")
        exporter = JSONDataExporter()

        import asyncio
        asyncio.run(exporter.save(self.sample_data, filename))
        with open(filename, encoding='utf-8') as f:
            data = json.load(f)
        self.assertEqual(data, self.sample_data)

    def test_excel_exporter(self):
        filename = os.path.join(self.tempdir.name, "test.xlsx")
        exporter = ExcelDataExporter()
        
        import asyncio
        asyncio.run(exporter.save(self.sample_data, filename))
        wb = openpyxl.load_workbook(filename)
        ws = wb.active
        if ws is None:
            raise ValueError("No active worksheet found")
        rows = list(ws.rows)
        header = [cell.value for cell in rows[0]]
        self.assertEqual(header, list(self.sample_data[0].keys()))
        self.assertEqual(rows[1][0].value, "Player 1")
        self.assertEqual(rows[2][0].value, "Player 2")

# Doctest for create_filter

def _doctest_create_filter():
    """
    >>> from app import create_filter
    >>> data = [
    ...     {"team_abbr": "A", "wins": 5},
    ...     {"team_abbr": "B", "wins": 2}
    ... ]
    >>> team_filter = create_filter(lambda x: x["team_abbr"] == "A")
    >>> team_filter(data)
    [{'team_abbr': 'A', 'wins': 5}]
    >>> win_filter = create_filter(lambda x: x["wins"] >= 3)
    >>> win_filter(data)
    [{'team_abbr': 'A', 'wins': 5}]
    """
    pass

if __name__ == "__main__":
    import doctest
    doctest.testmod()
    unittest.main()
