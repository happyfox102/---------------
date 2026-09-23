from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from pathlib import Path

from .storage import Store
from .numbers import number


def cell_address(text: str) -> str:
    spoken = text.lower().strip()
    letters = {"а": "A", "эй": "A", "б": "B", "бэ": "B", "би": "B", "си": "C", "цэ": "C", "ц": "C", "дэ": "D", "ди": "D", "д": "D", "е": "E", "и": "E", "эф": "F", "ф": "F", "джи": "G", "гэ": "G", "г": "G", "эйч": "H", "аш": "H"}
    parts = spoken.split(maxsplit=1)
    if len(parts) == 2 and (parts[0] in letters or re.fullmatch(r"[a-z]{1,3}", parts[0])):
        try:
            row = number(parts[1])
            if row == int(row):
                text = letters.get(parts[0], parts[0]) + str(int(row))
        except ValueError:
            pass
    text = text.strip().upper().replace(" ", "")
    text = text.translate(str.maketrans({"А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M", "О": "O", "Р": "P", "Т": "T", "Х": "X"}))
    if not re.fullmatch(r"[A-Z]{1,3}[1-9]\d{0,6}", text):
        raise ValueError("Нужен адрес ячейки, например B3 или А1.")
    from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
    column, row = coordinate_from_string(text)
    if column_index_from_string(column) > 16384 or row > 1048576:
        raise ValueError("Адрес за пределами листа Excel.")
    return text


class Office:
    def __init__(self, store: Store):
        self.store = store
        self.path: Path | None = None
        self.undo_stack: list[tuple[Path, Path]] = []

    def create(self, kind: str, title: str, text: str = "") -> Path:
        suffix = {"word": ".docx", "excel": ".xlsx", "txt": ".txt"}[kind]
        path = self.store.unique_path("documents", title, suffix)
        if kind == "word":
            from docx import Document
            doc = Document()
            for paragraph in text.split("\n"):
                doc.add_paragraph(paragraph)
            doc.save(path)
        elif kind == "excel":
            from openpyxl import Workbook
            book = Workbook()
            book.save(path)
            book.close()
            self.path = path
        else:
            path.write_text(text, encoding="utf-8")
        return path

    def select(self, source: str) -> Path:
        source_path = Path(source).resolve()
        if not source_path.is_file() or source_path.suffix.lower() != ".xlsx":
            raise ValueError("Выберите существующую книгу .xlsx.")
        from openpyxl import load_workbook
        book = load_workbook(source_path)
        book.close()
        documents = (self.store.data / "documents").resolve()
        if source_path.parent == documents:
            self.path = source_path
        else:
            self.path = self.store.unique_path("documents", source_path.stem + " — копия", ".xlsx")
            shutil.copy2(source_path, self.path)
        return self.path

    def _book(self):
        from openpyxl import load_workbook
        if self.path is None:
            raise ValueError("Сначала создайте таблицу или выберите книгу кнопкой «Выбрать Excel».")
        return load_workbook(self.path)

    def read(self, address: str) -> str:
        address = cell_address(address)
        book = self._book()
        try:
            value = book.active[address].value
            return "пусто" if value is None else str(value)
        finally:
            book.close()

    def change(self, action: str, address: str, value: str = ""):
        address = cell_address(address)
        book = self._book()
        backup = self.store.data / "backups" / (uuid.uuid4().hex + ".xlsx")
        temp = None
        try:
            sheet = book.active
            if action == "write":
                # Speech data stays text/numbers; never silently executes an Excel formula.
                try:
                    numeric = float(number(value))
                except ValueError:
                    sheet[address] = value
                    sheet[address].data_type = "s"
                else:
                    sheet[address] = int(numeric) if numeric.is_integer() else numeric
            elif action in ("copy", "cut"):
                dest = cell_address(value)
                if dest == address:
                    raise ValueError("Исходная ячейка и назначение совпадают.")
                sheet[dest].value = sheet[address].value
                sheet[dest].data_type = sheet[address].data_type
                if action == "cut":
                    sheet[address] = None
            elif action == "merge":
                dest = cell_address(value)
                from openpyxl.utils.cell import range_boundaries
                left, top, right, bottom = range_boundaries(f"{address}:{dest}")
                if right < left or bottom < top:
                    raise ValueError("Назовите сначала верхнюю левую, затем нижнюю правую ячейку.")
                if (right - left + 1) * (bottom - top + 1) > 10000:
                    raise ValueError("Для одной команды разрешено объединять до 10 000 ячеек.")
                for row in sheet.iter_rows(min_row=top, max_row=bottom, min_col=left, max_col=right):
                    for cell in row:
                        if cell.coordinate != address and cell.value is not None:
                            raise ValueError("Объединение удалит данные других ячеек. Сначала перенесите их.")
                sheet.merge_cells(f"{address}:{dest}")
            else:
                raise ValueError("Неизвестное действие с таблицей.")
            shutil.copy2(self.path, backup)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix=".xlsx", delete=False) as handle:
                temp = Path(handle.name)
            book.save(temp)
            os.replace(temp, self.path)
            self.undo_stack.append((self.path, backup))
        finally:
            book.close()
            if temp and temp.exists():
                temp.unlink()

    def _save_book(self, book, description: str) -> str:
        """Save a workbook atomically and keep one-step undo support."""
        backup = self.store.data / "backups" / (uuid.uuid4().hex + ".xlsx")
        temp = None
        try:
            shutil.copy2(self.path, backup)
            with tempfile.NamedTemporaryFile(dir=self.path.parent, suffix=".xlsx", delete=False) as handle:
                temp = Path(handle.name)
            book.save(temp)
            os.replace(temp, self.path)
            self.undo_stack.append((self.path, backup))
            return description
        finally:
            if temp and temp.exists():
                temp.unlink()

    def formula(self, target: str, expression: str) -> str:
        """Write a safe Excel formula (never evaluate arbitrary Python)."""
        target = cell_address(target)
        formula = expression.strip()
        if not formula.startswith("="):
            formula = "=" + formula
        if len(formula) > 400 or any(x in formula for x in ("[", "]", "\\", "!")):
            raise ValueError("Формула содержит недопустимую ссылку или слишком длинная.")
        if not re.fullmatch(r"=[A-Z][A-Z0-9_]*(?:\([^;]*\)|[A-Z0-9:,+*\-/(). ]*)", formula.upper()):
            raise ValueError("Поддерживается формула Excel с функциями SUM, AVERAGE, MIN, MAX или IF.")
        book = self._book()
        try:
            book.active[target] = formula
            book.active[target].data_type = "f"
            result = self._save_book(book, f"Формула записана в {target}: {formula}")
            return result
        finally:
            book.close()

    def fill_formula(self, target_column: str, expression: str, start_row: int = 2, end_row: int | None = None) -> str:
        """Fill a formula down a column, translating relative references per row."""
        col = target_column.strip().upper()
        if not re.fullmatch(r"[A-Z]{1,3}", col):
            raise ValueError("Укажите столбец Excel, например D.")
        book = self._book()
        try:
            sheet = book.active
            if end_row is None:
                end_row = max((c.row for row in sheet.iter_rows() for c in row if c.value is not None), default=start_row)
            if not (1 <= start_row <= end_row <= 1048576) or end_row - start_row > 10000:
                raise ValueError("Диапазон расчёта должен содержать от 1 до 10 000 строк.")
            formula = expression.strip()
            if not formula.startswith("="):
                formula = "=" + formula
            if len(formula) > 400 or any(x in formula for x in ("[", "]", "\\")):
                raise ValueError("Формула содержит недопустимую ссылку или слишком длинная.")
            from openpyxl.formula.translate import Translator
            for row in range(start_row, end_row + 1):
                cell = f"{col}{row}"
                sheet[cell] = Translator(formula, origin=cell).translate_formula(cell)
            return self._save_book(book, f"Формула заполнена в столбце {col}: строки {start_row}–{end_row}.")
        finally:
            book.close()

    def chart(self, source_range: str, chart_type: str = "bar", title: str = "Диаграмма") -> str:
        """Create a chart from a rectangular range on the active sheet."""
        from openpyxl.chart import BarChart, LineChart, PieChart, Reference
        from openpyxl.utils.cell import range_boundaries
        left, top, right, bottom = range_boundaries(source_range.replace("$", "").upper())
        if right - left < 1 or bottom - top < 1 or (right-left+1) * (bottom-top+1) > 10000:
            raise ValueError("Укажите прямоугольный диапазон минимум из двух столбцов и двух строк.")
        book = self._book()
        try:
            sheet = book.active
            kind = chart_type.lower()
            chart = PieChart() if kind in ("pie", "круговая", "круг") else LineChart() if kind in ("line", "линейная", "график") else BarChart()
            data = Reference(sheet, min_col=left + 1, max_col=right, min_row=top, max_row=bottom)
            categories = Reference(sheet, min_col=left, min_row=top + 1, max_row=bottom)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)
            chart.title = title[:120]
            chart.style = 10
            sheet.add_chart(chart, f"{chr(64 + min(right + 2, 26))}2")
            return self._save_book(book, f"Диаграмма создана по диапазону {source_range}.")
        finally:
            book.close()

    def undo(self) -> str:
        if not self.undo_stack:
            return "Нет изменений Excel для отмены в этом сеансе."
        path, backup = self.undo_stack[-1]
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".xlsx", delete=False) as handle:
            temp = Path(handle.name)
        try:
            shutil.copy2(backup, temp)
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)
        self.undo_stack.pop()
        return f"Последнее изменение отменено: {path.name}."
