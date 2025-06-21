import csv
import json
from abc import ABC, abstractmethod
import logging
from typing import List

import openpyxl


class DataExporter(ABC):
    @abstractmethod
    async def save(self, data: List[dict], filename: str) -> bool:
        pass


class CSVDataExporter(DataExporter):
    async def save(self, data: List[dict], filename: str) -> bool:
        logging.info(f"Exporting data to CSV: {filename}")
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                if data and len(data) > 0:
                    writer.writerow(data[0].keys())
                    for row in data:
                        writer.writerow(row.values())
        except Exception as e:
            logging.error(f"Error saving to CSV: {e}")
            return False
        logging.info(f"Successfully exported data to CSV: {filename}")
        return True


class JSONDataExporter(DataExporter):
    async def save(self, data: List[dict], filename: str) -> bool:
        logging.info(f"Exporting data to JSON: {filename}")
        try:
            with open(filename, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"Error saving to JSON: {e}")
            return False
        logging.info(f"Successfully exported data to JSON: {filename}")
        return True


class ExcelDataExporter(DataExporter):
    async def save(self, data: List[dict], filename: str) -> bool:
        logging.info(f"Exporting data to Excel: {filename}")
        
        try:
            wb = openpyxl.Workbook()
        except Exception as e:
            logging.error(f"Error creating workbook: {e}")
            return False
        
        ws = wb.active
        if ws is None:
            logging.error("Could not get active worksheet from workbook.")
            return False
        
        if data and len(data) > 0:
            try:
                ws.append(list(data[0].keys()))
                for row in data:
                    row = [
                        str(v) if isinstance(v, (dict, list)) else v
                        for v in row.values()
                    ]
                    ws.append(row)
            except Exception as e:
                logging.error(f"Error writing data to worksheet: {e}")
                return False
        try:
            wb.save(filename)
        except Exception as e:
            logging.error(f"Error saving Excel file: {e}")
            return False
        
        logging.info(f"Successfully exported data to Excel: {filename}")
        return True
