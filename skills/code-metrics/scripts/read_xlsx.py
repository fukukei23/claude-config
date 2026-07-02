import openpyxl
wb = openpyxl.load_workbook('/mnt/c/Users/yn441/Downloads/技術経歴書.xlsx', data_only=True)
for sh in wb.sheetnames:
    ws = wb[sh]
    print(f"=== {sh} ===")
    for row in ws.iter_rows(values_only=True):
        if any(cell is not None for cell in row):
            print(row)
