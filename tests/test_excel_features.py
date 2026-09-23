import tempfile
import unittest
from pathlib import Path

from openpyxl import load_workbook

from friday.office import Office
from friday.storage import Store
from friday.engine import Engine


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

    def test_plain_language_commands(self):
        with tempfile.TemporaryDirectory() as temp:
            engine = Engine(Store(Path(temp)))
            engine.office.create("excel", "plain-language")
            for row in range(2, 5):
                engine.office.change("write", f"A{row}", str(row))
                engine.office.change("write", f"B{row}", str(row * 10))
            self.assertIn("Формула записана", engine.execute("посчитай сумму из A2:A4 в C2"))
            self.assertIn("Формула заполнена", engine.execute("в столбце D сложи столбцы A и B с 2 по 4"))
            self.assertIn("Диаграмма создана", engine.execute("построй линейный график по A1:B4 с названием Продажи"))


if __name__ == "__main__":
    unittest.main()
