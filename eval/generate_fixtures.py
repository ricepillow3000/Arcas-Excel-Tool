"""Writes 5 small .xlsx sheets, each from its own domain, with 3 planted errors and 3 honest quirks, and
ground_truth.json naming their cells. Formulas are written as formulas and LibreOffice recalculates each file, so
the cells carry the values Excel would show. Needs `soffice` on PATH. Usage: python eval/generate_fixtures.py"""
import json
import random
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

import openpyxl

HERE = Path(__file__).parent
N = 60


def saas(r):
    head = ["Customer", "Plan", "Seats", "Price per seat", "MRR", "Region"]
    plans = {"Starter": 15, "Team": 29, "Business": 49}
    rows = []
    for i in range(N):
        plan = r.choice(list(plans))
        rows.append([f"Acme {i + 1:03d}", plan, r.randint(3, 40), plans[plan], f"=C{i + 2}*D{i + 2}",
                     r.choice(["NA", "EMEA", "APAC"])])
    rows[11][4] = 1234  # a number typed over the MRR formula
    rows[23][2] = 250  # seats 25 typed with an extra zero
    rows[37][5] = "EMAE"  # a region misspelt
    rows[5][1:4] = ["Enterprise", 900, 39]  # one real enterprise account
    rows[19][1:4] = ["Free", 2, 0]  # a free plan pays nothing
    rows[44][1:4] = ["Business", 3, 49]  # the smallest real Business account
    return head, rows, ["E13", "C25", "F39"], ["C7", "D21", "C46"]


def inventory(r):
    head = ["SKU", "Item", "Category", "Qty on hand", "Unit cost", "Stock value", "Last counted"]
    cats = {"Fasteners": 0.4, "Tools": 25, "Electrical": 8}
    rows = []
    for i in range(N):
        cat = r.choice(list(cats))
        rows.append([f"SKU-{1000 + i}", f"{cat} item {i}", cat, r.randint(20, 200),
                     round(cats[cat] * r.uniform(0.8, 1.2), 2), f"=D{i + 2}*E{i + 2}",
                     date(2026, 10, 1) + timedelta(days=r.randint(0, 50))])
    rows[8][5] = "=D10*E11"  # a formula one row off
    rows[30][6] = date(2084, 10, 14)  # a count dated 2084
    rows[47][3] = "twelve"  # a word in a number column
    rows[14][3] = 0  # sold out
    rows[22][2:5] = ["Fasteners", 5000, 0.02]  # a bulk box of washers
    rows[40][2:5] = ["Tools", 1, 4800]  # one bench lathe
    return head, rows, ["F10", "G32", "D49"], ["D16", "D24", "E42"]


def crm(r):
    head = ["Lead ID", "Company", "Stage", "Deal value", "Created", "Closed"]
    rows = []
    for i in range(N):
        made = date(2026, 1, 5) + timedelta(days=r.randint(0, 200))
        rows.append([f"L-{5000 + i}", f"Company {i + 1}", r.choice(["Won", "Lost", "Negotiation"]),
                     round(r.uniform(8000, 30000), -2), made, made + timedelta(days=r.randint(10, 90))])
    rows[16][5] = rows[16][4] - timedelta(days=30)  # closed a month before it was created
    rows[28][2] = "Negotation"  # a stage misspelt
    rows[49][3] = rows[49][3] * 100  # a deal value with two extra zeros
    rows[3][3] = 0  # a lost deal worth nothing
    rows[33][5] = rows[33][4]  # closed the day it was created
    rows[52][3] = 61000  # the year's biggest real deal
    return head, rows, ["F18", "C30", "D51"], ["D5", "F35", "D54"]


def payroll(r):
    head = ["Employee ID", "Department", "Hours", "Rate", "Gross", "Tax", "Net"]
    rows = []
    for i in range(N):
        rows.append([f"E{100 + i}", r.choice(["Engineering", "Sales", "Support"]), r.choice([38, 40, 40, 42]),
                     round(r.uniform(22, 45), 2), f"=C{i + 2}*D{i + 2}", f"=ROUND(E{i + 2}*0.2,2)",
                     f"=E{i + 2}-F{i + 2}"])
    rows[9][6] = 2500  # a number typed over the Net formula
    rows[25][2] = 400  # 40 hours typed with an extra zero
    rows[41][1] = "Enginering"  # a department misspelt
    rows[13][2:4] = [40, 180]  # the CEO's rate
    rows[30][2] = 8  # a part-timer's one shift
    rows[52][2] = 60  # a week of overtime
    return head, rows, ["G11", "C27", "B43"], ["D15", "C32", "C54"]


def lab(r):
    head = ["Sample ID", "Patient", "Test", "Value", "Unit", "Collected"]
    tests = {"Sodium": (140, 2.5, "mmol/L"), "Potassium": (4.2, 0.3, "mmol/L"), "Glucose": (95, 9, "mg/dL")}
    rows = []
    for i in range(N):
        test = list(tests)[i % 3]
        mean, sd, unit = tests[test]
        rows.append([f"S-{9000 + i}", f"P{200 + i // 3}", test, round(r.gauss(mean, sd), 1), unit,
                     date(2026, 11, 2) + timedelta(days=i // 6)])
    rows[10][3] = 42  # potassium 4.2 with its decimal point lost
    rows[20][3] = -rows[20][3]  # a glucose with a minus sign
    rows[30][3] = "pending"  # a word in the value column
    rows[11][3] = 128.0  # a real low sodium
    rows[14][3] = 6.1  # a real high potassium (row 16 is a Potassium test)
    rows[35][3] = 380.0  # a real diabetic glucose
    return head, rows, ["D12", "D22", "D32"], ["D13", "D16", "D37"]


def main():
    truth = {}
    with tempfile.TemporaryDirectory() as tmp:
        for k, build in enumerate((saas, inventory, crm, payroll, lab)):
            head, rows, errors, quirks = build(random.Random(k))
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(head)
            for row in rows:
                ws.append(row)
            name = f"{build.__name__}.xlsx"
            wb.save(Path(tmp, name))
            subprocess.run(["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(Path(tmp, "out")),
                            str(Path(tmp, name))], check=True, capture_output=True)
            shutil.copy(Path(tmp, "out", name), HERE / name)
            truth[name] = {"errors": errors, "quirks": quirks}
    (HERE / "ground_truth.json").write_text(json.dumps(truth, indent=2) + "\n")


if __name__ == "__main__":
    main()
