import os
import openpyxl
import re

_candidates = ['/mnt/c/Users/yn441/Downloads/技術経歴書.xlsx', os.path.expanduser('~/Downloads/技術経歴書.xlsx')]
path = next((p for p in _candidates if os.path.exists(p)), _candidates[0])
wb = openpyxl.load_workbook(path)
ws = wb.active

updated = []
for row in ws.iter_rows():
    for cell in row:
        if cell.value and isinstance(cell.value, str):
            original = cell.value
            # atelier の 1,488件 → 2,070件
            new_val = re.sub(r'1,488件', '2,070件', cell.value)
            # atelier の 1488 → 2070（数字のみ）
            new_val = re.sub(r'\b1488\b', '2070', new_val)
            if new_val != original:
                cell.value = new_val
                updated.append(f"行{cell.row}列{cell.column}: {repr(original[:60])} → {repr(new_val[:60])}")

wb.save(path)
if updated:
    for u in updated:
        print(f"✅ {u}")
else:
    print("変更なし（該当セルなし）")
