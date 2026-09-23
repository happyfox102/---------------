import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from friday.office import Office
from friday.storage import Store


class ExcelFeaturesTests(unittest.TestCase):
    def test_formulas_fill_and_chart_are_saved(self):
        with tempfile.TemporaryDirectory() as temp:
            office = Office(Store(Path(temp)))
            office.create("excel", "analytics")
            for row, (label, value) in enumerate((("Mon", 10), ("Tue", 20), ("Wed", 30)), 2):
                office.change("write", f"A{row}", label)
                office.change("write", f"B{row}", str(value))
            office.formula("C2", "=SUM(B2:B2)")
            office.fill_formula("C", "=SUM(B2:B2)", 2, 4)
            office.chart("A1:B4", "line", "Sales")
            book = load_workbook(office.path)
            self.assertEqual(book.active["C2"].value, "=SUM(B2:B2)")
            self.assertEqual(len(book.active._charts), 1)
            book.close()


if __name__ == "__main__":
    unittest.main()
