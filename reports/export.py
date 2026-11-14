"""Tables of the Reports hub: one structure for the HTML table, the CSV file and the XLSX file."""
import csv
import io
import re

from django.http import HttpResponse
from django.utils.formats import number_format

MONEY, NUMBER, PERCENT, INTEGER, TEXT = 'money', 'number', 'percent', 'integer', 'text'
_NUMERIC = (MONEY, NUMBER, PERCENT, INTEGER)


class Table:
    """A report table.

    columns: list of (key, label, kind) with kind one of TEXT / MONEY / NUMBER / PERCENT / INTEGER
    rows:    list of dicts keyed by column key; a row may carry extra keys (e.g. "url", "highlight")
    """

    def __init__(self, key, title, columns, rows, total=None, limit=None):
        self.key, self.title, self.columns, self.rows, self.total = key, title, columns, rows, total
        self.limit = limit      # rows shown on the page; the exported file always has all rows

    def __bool__(self):
        return bool(self.rows)

    @staticmethod
    def _format(value, kind):
        if value is None or value == '':
            return '–'
        if kind == MONEY:
            return number_format(value, 2, use_l10n=True, force_grouping=True)
        if kind == NUMBER:
            return number_format(round(float(value), 3), None, use_l10n=True, force_grouping=True)
        if kind == PERCENT:
            return f'{number_format(value, 1, use_l10n=True)} %'
        if kind == INTEGER:
            return number_format(int(value), 0, use_l10n=True, force_grouping=True)
        return str(value)

    def _cells(self, row):
        return [{'text': self._format(row.get(key), kind), 'numeric': kind in _NUMERIC,
                 'url': row.get('url') if index == 0 else None,
                 'highlight': key in (row.get('highlight') or ())}
                for index, (key, _label, kind) in enumerate(self.columns)]

    def header(self):
        return [{'label': label, 'numeric': kind in _NUMERIC} for _key, label, kind in self.columns]

    def display_rows(self):
        rows = self.rows[:self.limit] if self.limit else self.rows
        return [self._cells(row) for row in rows]

    def hidden_rows(self):
        return max(len(self.rows) - self.limit, 0) if self.limit else 0

    def display_total(self):
        return self._cells(self.total) if self.total else None

    # -- files -------------------------------------------------------------------------------------
    def _raw_rows(self):
        rows = self.rows + ([self.total] if self.total else [])
        for row in rows:
            yield [self._raw(row.get(key), kind) for key, _label, kind in self.columns]

    @staticmethod
    def _raw(value, kind):
        if value is None:
            return ''
        if kind in (MONEY, PERCENT):
            return round(float(value), 2)
        if kind == NUMBER:
            return round(float(value), 3)
        if kind == INTEGER:
            return int(value)
        return str(value)

    def filename(self, extension):
        return f'{re.sub(r"[^a-z0-9_]+", "_", self.key.lower())}.{extension}'

    def csv_response(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=';')
        writer.writerow([label for _key, label, _kind in self.columns])
        writer.writerows(self._raw_rows())
        # BOM so that Excel opens Cyrillic text correctly
        response = HttpResponse('﻿' + buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{self.filename("csv")}"'
        return response

    def xlsx_response(self):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        from openpyxl.utils import get_column_letter

        book = Workbook()
        sheet = book.active
        sheet.title = re.sub(r'[\[\]:*?/\\]', ' ', str(self.title))[:31] or 'Report'
        sheet.append([str(label) for _key, label, _kind in self.columns])
        for cell in sheet[1]:
            cell.font = Font(bold=True)
        for row in self._raw_rows():
            sheet.append(row)
        for index, (_key, label, kind) in enumerate(self.columns, start=1):
            letter = get_column_letter(index)
            sheet.column_dimensions[letter].width = max(12, min(48, len(str(label)) + 4)) if kind != TEXT else 32
            if kind in (MONEY, PERCENT):
                for cell in sheet[letter][1:]:
                    cell.number_format = '#,##0.00'
        sheet.freeze_panes = 'A2'
        buffer = io.BytesIO()
        book.save(buffer)
        response = HttpResponse(
            buffer.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{self.filename("xlsx")}"'
        return response

    def response(self, file_format):
        return self.xlsx_response() if file_format == 'xlsx' else self.csv_response()
