#file: run_dmm.py
#purpose: Reads the DMM workbook, runs it through the backend (UqSpace-DMM Version 1.py)
#         and writes the answers into the workbook's Results sheet
#usage: double-click "Run DMM.exe" (or run this file) in the folder with the workbook,
#       or drag a workbook onto the exe
#editor: Jamie

import datetime
import glob
import importlib.util
import os
import sys

import numpy as np                     
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font

BACKEND_NAME = "UqSpace-DMM Version 1.py"
WORKBOOK_NAME = "UQSpace - Decision Making Matrix.xlsx"
MAX_CRITERIA = 10
MAX_ALTERNATIVES = 30

#folder the exe (or script) lives in
if getattr(sys, "frozen", False):
    HERE = os.path.dirname(sys.executable)
    BUNDLED = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = BUNDLED = os.path.dirname(os.path.abspath(__file__))


#function: load_backend
#return: the backend module (ahp, consistency_ratio, topsis)
#uses the backend .py next to the exe if there is one, so edits take effect without rebuilding,
#otherwise the copy that was bundled into the exe when it was built
def load_backend():
    for folder in (HERE, BUNDLED):
        path = os.path.join(folder, BACKEND_NAME)
        if os.path.exists(path):
            spec = importlib.util.spec_from_file_location("uqspace_backend", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, path
    raise RuntimeError(f"Error R-01: can't find '{BACKEND_NAME}'. Put it in the same folder as this program.")


#function: find_workbook
#return: path of the workbook to use
def find_workbook():
    files = [a for a in sys.argv[1:] if not a.startswith("--")]
    if files:                                          #a file was dragged onto the exe
        return os.path.abspath(files[0])
    preferred = os.path.join(HERE, WORKBOOK_NAME)
    if os.path.exists(preferred):
        return preferred
    candidates = []
    for path in glob.glob(os.path.join(HERE, "*.xlsx")):
        if os.path.basename(path).startswith("~$"):    #Excel's lock file
            continue
        try:
            if {"Criteria", "Comparisons", "Alternatives"} <= set(load_workbook(path, read_only=True).sheetnames):
                candidates.append(path)
        except Exception:
            pass
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise RuntimeError(f"Error R-02: no DMM workbook in {HERE}. Put '{WORKBOOK_NAME}' in the same folder as this program.")
    raise RuntimeError("Error R-03: more than one DMM workbook in this folder. Drag the one you want onto the program.")


#function: wait_until_closed
#param: path, workbook path
#Excel locks a workbook while it is open, so we can't write the results until it is closed
def wait_until_closed(path):
    while True:
        try:
            with open(path, "r+b"):
                return
        except PermissionError:
            input(f"\n'{os.path.basename(path)}' is open in Excel.\n"
                  "Save your changes, close it, then press Enter to continue...")



######## #Reading the inputs ######################################################3

def is_blank(value):
    return value is None or str(value).strip() == ""


#function: read_criteria
#return: names (list of str), benefit (list of bool, True = higher is better)
def read_criteria(wb):
    ws = wb["Criteria"]
    names, benefit, gap = [], [], False
    for row in range(2, 2 + MAX_CRITERIA):
        name, better = ws.cell(row=row, column=1).value, ws.cell(row=row, column=2).value
        if is_blank(name):
            gap = True
            continue
        if gap:
            raise ValueError(f"Error V-01: the Criteria sheet has an empty row above row {row}. Remove the gap.")
        name = str(name).strip()
        if name in names:
            raise ValueError(f"Error V-02: criterion '{name}' is listed twice. Each name must be unique.")
        better = "Higher" if is_blank(better) else str(better).strip().capitalize()
        if better not in ("Higher", "Lower"):
            raise ValueError(f"Error V-03: 'Better when' for {name} must be Higher or Lower.")
        names.append(name)
        benefit.append(better == "Higher")
    if len(names) < 2:
        raise ValueError("Error V-04: enter at least two criteria on the Criteria sheet.")
    return names, benefit


#function: parse_scale
#param: value, e.g. 7, "7", "1/7" or 0.142857
#return: the value as a float, or None if it isn't on the 1/9 to 9 scale
def parse_scale(value):
    text = str(value).strip()
    try:
        if "/" in text:
            top, bottom = text.split("/")
            x = float(top) / float(bottom)
        else:
            x = float(text)
    except (ValueError, ZeroDivisionError):
        return None
    for k in range(1, 10):
        if abs(x - k) < 1e-3:
            return float(k)
        if abs(x - 1 / k) < 1e-3:
            return 1 / k
    return None


#function: read_comparisons
#return: matrix (n x n AHP comparison matrix), threshold (CR limit, 0 = backend default)
def read_comparisons(wb, names):
    ws = wb["Comparisons"]
    n = len(names)
    matrix = np.ones((n, n))
    #only the cells above the diagonal are read; the ones below just display the reciprocals
    for i in range(n):
        for j in range(i + 1, n):
            cell = ws.cell(row=2 + i, column=2 + j)
            where = f"{names[i]} (row) vs {names[j]} (column), cell {cell.coordinate}"
            if is_blank(cell.value):
                raise ValueError(f"Error V-05: fill in {where} on the Comparisons sheet.")
            value = parse_scale(cell.value)
            if value is None:
                raise ValueError(f"Error V-06: {where} must be 1 to 9 or 1/2 to 1/9, not '{cell.value}'.")
            matrix[i, j] = value
            matrix[j, i] = 1 / value

    #the backend treats 0 as "use the default of 0.1"
    limit = ws.cell(row=MAX_CRITERIA + 7, column=2).value
    try:
        threshold = 0 if is_blank(limit) else float(limit)
    except ValueError:
        raise ValueError("Error V-07: the consistency limit on the Comparisons sheet must be a number.")
    return matrix, threshold


#function: read_alternatives
#return: alts (list of names), values (m x n decision matrix)
def read_alternatives(wb, names):
    ws = wb["Alternatives"]
    n = len(names)
    alts, values = [], []
    for row in range(2, 2 + MAX_ALTERNATIVES):
        name = ws.cell(row=row, column=1).value
        cells = [ws.cell(row=row, column=2 + j).value for j in range(n)]
        if is_blank(name):
            if any(not is_blank(v) for v in cells):
                raise ValueError(f"Error V-08: row {row} on the Alternatives sheet has values but no name.")
            continue
        name = str(name).strip()
        if name in alts:
            raise ValueError(f"Error V-09: alternative '{name}' is listed twice.")
        rowValues = []
        for j, v in enumerate(cells):
            try:
                rowValues.append(float(v))
            except (TypeError, ValueError):
                raise ValueError(f"Error V-10: {name} needs a number for {names[j]} (row {row}).")
        if any(v < 0 for v in rowValues):
            raise ValueError(f"Error V-11: {name} has a negative value. Use positive values only.")
        alts.append(name)
        values.append(rowValues)
    if len(alts) < 2:
        raise ValueError("Error V-12: enter at least two alternatives on the Alternatives sheet.")
    return alts, np.array(values)



################## Writing the Results sheet ##################################

#function: fresh_results_sheet
#return: an empty Results sheet in the same position, plus the header/body styles to use
def fresh_results_sheet(wb):
    crit = wb["Criteria"]
    styles = {"head_first": crit["A1"]._style, "head": crit["B1"]._style,
              "body_first": crit["A2"]._style, "body": crit["B2"]._style}
    font = crit["A2"].font.name
    index = wb.sheetnames.index("Results") if "Results" in wb.sheetnames else len(wb.sheetnames)
    if "Results" in wb.sheetnames:
        del wb["Results"]
    return wb.create_sheet("Results", index), styles, font


def table(ws, styles, top, left, headers, rows, formats):
    from copy import copy
    for c, h in enumerate(headers):
        cell = ws.cell(row=top, column=left + c, value=h)
        cell._style = copy(styles["head_first" if c == 0 else "head"])
        cell.alignment = Alignment(horizontal="left" if c == 0 else "center", vertical="center")
    for r, values in enumerate(rows, start=1):
        for c, v in enumerate(values):
            cell = ws.cell(row=top + r, column=left + c, value=v)
            cell._style = copy(styles["body_first" if c == 0 else "body"])
            if formats[c]:
                cell.number_format = formats[c]
            if c > 0:
                cell.alignment = Alignment(horizontal="center")


def write_error(wb, message):
    ws, styles, font = fresh_results_sheet(wb)
    ws["A1"] = "Results"
    ws["A1"].font = Font(name=font, bold=True, size=14)
    ws["A3"] = message
    ws["A3"].font = Font(name=font, bold=True, color="C00000")
    ws["A4"] = "Fix this, save, close the workbook and run the program again."
    ws["A4"].font = Font(name=font, italic=True, color="595959")
    ws["A6"] = f"Last run: {datetime.datetime.now():%d/%m/%Y %H:%M}"
    ws["A6"].font = Font(name=font, italic=True, color="808080")
    ws.column_dimensions["A"].width = 30


def write_results(wb, names, benefit, matrix, weights, eigenvalue, CR, consistent, limit, alts, C, ranking):
    ws, styles, font = fresh_results_sheet(wb)
    n = len(names)
    ws.column_dimensions["A"].width = 30
    for col in "BCDEFGHIJK":
        ws.column_dimensions[col].width = 18

    ws["A1"] = "Results"
    ws["A1"].font = Font(name=font, bold=True, size=14)
    best = ranking[0]
    ws["A2"] = f"Best option: {alts[best]} ({C[best] * 100:.1f}% of the way to the ideal design)"
    ws["A2"].font = Font(name=font, bold=True, size=12)
    if consistent:
        ws["A3"] = f"Criteria comparisons are consistent (CR {CR:.3f}, limit {limit:g})."
        ws["A3"].font = Font(name=font, color="375623")
    else:
        ws["A3"] = (f"Warning: criteria comparisons are inconsistent (CR {CR:.3f}, limit {limit:g}). "
                    "Revisit the Comparisons sheet before relying on this ranking.")
        ws["A3"].font = Font(name=font, bold=True, color="C00000")
    ws["A4"] = f"Last run: {datetime.datetime.now():%d/%m/%Y %H:%M}. Run the program again after changing any inputs."
    ws["A4"].font = Font(name=font, italic=True, color="808080")

    #ranking
    rows = [[alts[i], r, float(C[i])] for r, i in enumerate(ranking, start=1)]
    table(ws, styles, 6, 1, ["Alternative", "Rank", "Closeness"], rows, [None, "0", "0.0%"])

    #weights
    rows = [[names[k], "Higher" if benefit[k] else "Lower", float(weights[k])] for k in range(n)]
    table(ws, styles, 6, 5, ["Criterion", "Better when", "Weight"], rows, [None, None, "0.0%"])

    #consistency check
    CI = (eigenvalue - n) / (n - 1) if n > 2 else 0.0
    rows = [["Dominant eigenvalue", float(eigenvalue)], ["Consistency index", float(CI)],
            ["Consistency ratio", float(CR)], ["Limit", float(limit)],
            ["Consistent", "Yes" if consistent else "No"]]
    table(ws, styles, 6, 9, ["Consistency check", "Value"], rows, [None, "0.000"])

    #comparison matrix used
    top = 8 + max(len(alts), n, 5)
    ws.cell(row=top - 1, column=1, value="Comparison matrix used (row vs column)").font = Font(name=font, bold=True)
    asText = lambda x: f"{x:g}" if x >= 1 else f"1/{1 / x:g}"
    rows = [[names[i]] + [asText(x) for x in matrix[i]] for i in range(n)]
    table(ws, styles, top, 1, ["Row vs column"] + names, rows, [None] * (n + 1))



############### Main ##############################################################################3

def main():
    print("UQ Space decision-making matrix\n")
    backend, backendPath = load_backend()
    path = find_workbook()
    print(f"Workbook: {os.path.basename(path)}")
    print(f"Backend:  {backendPath if os.path.dirname(backendPath) == HERE else BACKEND_NAME + ' (built in)'}\n")
    wait_until_closed(path)

    wb = load_workbook(path)
    for sheet in ("Criteria", "Comparisons", "Alternatives"):
        if sheet not in wb.sheetnames:
            raise RuntimeError(f"Error R-04: the workbook has no '{sheet}' sheet.")

    try:
        names, benefit = read_criteria(wb)
        matrix, threshold = read_comparisons(wb, names)
        alts, values = read_alternatives(wb, names)
    except ValueError as e:
        write_error(wb, str(e))
        wb.calculation.fullCalcOnLoad = True
        wb.save(path)
        print(e)
        print("\nThe message has also been written to the Results sheet.")
        return path, False

    #the backend does all the maths
    weights, eigenvalue = backend.ahp(matrix)
    CR, consistent = backend.consistency_ratio(eigenvalue, matrix, threshold)
    C, ranking = backend.topsis(values, weights, benefit)
    limit = threshold if threshold != 0 else 0.1

    write_results(wb, names, benefit, matrix, weights, eigenvalue, CR, consistent, limit, alts, C, ranking)
    wb.active = wb.sheetnames.index("Results")
    for ws in wb.worksheets:
        ws.sheet_view.tabSelected = ws.title == "Results"
    wb.calculation.fullCalcOnLoad = True
    wb.save(path)

    print("Weights:")
    for name, w in zip(names, weights):
        print(f"  {name:<20} {w * 100:5.1f}%")
    print(f"\nConsistency ratio: {CR:.3f} -> {'consistent' if consistent else 'INCONSISTENT, check the Comparisons sheet'}")
    print("\nRanking:")
    for rank, i in enumerate(ranking, start=1):
        print(f"  {rank}. {alts[i]:<20} {C[i] * 100:5.1f}%")
    print("\nResults saved to the Results sheet.")
    return path, True


if __name__ == "__main__":
    path = None
    try:
        path, _ = main()
    except Exception as e:
        print(f"\n{e}")
    if path and os.name == "nt" and "--no-open" not in sys.argv:
        try:
            os.startfile(path)        #reopen the workbook on the Results sheet
        except OSError:
            pass
    if sys.stdin and sys.stdin.isatty() and "--no-open" not in sys.argv:
        input("\nPress Enter to close...")
