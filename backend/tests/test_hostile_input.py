"""AH-185: four guards on input that reaches the engine from outside the pane. Each one was missing or weaker in the
shipped app than on the machine the tests ran on, so each is pinned here both ways (the wrong refused, the right let
through at its very limit). Crafted files only, built in the test: no binary fixture is committed.
  1. the XML parser openpyxl uses to read a workbook (hardened only while defusedxml is installed)
  2. how big a file may unpack to (the CLI reads files from disk, where no HTTP cap applies)
  3. /fix's start_row (bounded like /scan's)
  4. an invite kit's invite-code.txt (checked like a pasted code)
"""
import tomllib
import zipfile
from pathlib import Path

import openpyxl.xml
import pandas as pd
import pytest
from test_api_security import _fake_dpapi  # Windows' DPAPI as a test can run it anywhere (read only: that file is AH-189-locked)

from anomaly_hunter import app, sealed, server
from anomaly_hunter.ai import client
from anomaly_hunter.engine import load

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- 1. the workbook XML parser the shipped exe uses

def test_the_engine_reads_a_workbooks_xml_with_the_hardened_parser():
    # openpyxl swaps in defusedxml's parser only when defusedxml is importable, so a billion-laughs entity or an
    # external entity in sheet XML is refused. Nothing in the engine calls defusedxml: this is the only thing that
    # says whether the hardening is on, and it must be on wherever the engine runs, not only on a dev machine.
    assert openpyxl.xml.DEFUSEDXML is True
    assert load.defusedxml, "engine/load.py must import defusedxml: openpyxl hardens its parser only when it can"


def test_defusedxml_is_declared_for_every_install_the_exe_is_built_from():
    # AH-185: defusedxml was in neither `dependencies` nor the `exe` extra, and constraints.txt only pinned it (a
    # constraint caps a version, it does not install one). It reached a dev machine through the dev extra's transitive
    # graph alone, so `pip install -e ".[exe]" -c constraints.txt` in build-exe.yml built an exe without it: dev and CI
    # refused hostile XML entities and the Arcas.exe users run did not.
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert "defusedxml==0.7.1" in project["dependencies"], project["dependencies"]
    pins = [line.strip() for line in (ROOT / "constraints.txt").read_text(encoding="utf-8").splitlines()
            if line.startswith("defusedxml==")]
    assert pins == ["defusedxml==0.7.1"], pins  # the same pin in both files: a constraint that moves alone installs nothing


# ---------------------------------------------------------------- 2. how big a file may unpack to

def _zip_that_declares(path, name, data, declared):
    """A small zip whose central directory declares `declared` unpacked bytes: what a zip bomb looks like to
    zipfile.infolist(), without writing gigabytes inside a test."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(name, data)
    raw = bytearray(path.read_bytes())
    at = raw.index(b"PK\x01\x02") + 24  # the central directory's uncompressed size, 4 bytes little-endian
    raw[at:at + 4] = declared.to_bytes(4, "little")
    path.write_bytes(raw)
    return path


def test_a_workbook_of_two_kilobytes_that_unpacks_to_gigabytes_is_refused_in_the_engines_own_words(tmp_path):
    # a .xlsx is a zip: 2 KB on disk can be gigabytes of sheet XML, which filled the PC's memory before any check ran.
    # server.py's MAX_CELLS and MAX_CONTENT_LENGTH guard the pane's HTTP path only; the CLI reads a file off the disk.
    path = _zip_that_declares(tmp_path / "hostile.xlsx", "xl/worksheets/sheet1.xml", b"<worksheet/>", 1_610_612_736)
    assert path.stat().st_size < 2048  # the bomb's shape: tiny on disk, 1.5 GB once unpacked
    assert zipfile.ZipFile(path).infolist()[0].file_size == 1_610_612_736  # what the guard reads
    with pytest.raises(load.LoadError) as e:
        load.load_inputs([path])
    assert str(e.value) == ("Could not read hostile.xlsx: it unpacks to about 1.5 GB, far more than a real sheet "
                            "(1 GB at most). Check where the file came from."), str(e.value)


def test_a_file_exactly_at_the_unpacked_ceiling_loads_and_one_byte_past_it_is_refused(tmp_path, monkeypatch):
    # the guard at its very limit, on the .csv path (a csv is measured by its own size on disk)
    text = "Note\n" + "".join(f"row {i}\n" for i in range(200))
    path = tmp_path / "notes.csv"
    path.write_text(text, encoding="utf-8", newline="")
    assert path.stat().st_size == len(text)
    monkeypatch.setattr(load, "MAX_UNPACKED", len(text))
    df = load.load_inputs([path])[0]
    assert list(df["Note"])[:2] == ["row 0", "row 1"]
    monkeypatch.setattr(load, "MAX_UNPACKED", len(text) - 1)
    with pytest.raises(load.LoadError, match="far more than a real sheet"):
        load.load_inputs([path])


def test_a_real_workbook_of_the_size_arcas_is_meant_for_still_loads(tmp_path):
    path = tmp_path / "orders.xlsx"
    # Qty repeats: 500 near-sequential whole numbers would read as an ID (load._is_id), not a quantity
    pd.DataFrame({"Id": [f"A{i}" for i in range(500)], "Qty": [i % 7 + 1 for i in range(500)],
                  "Price": [1.5 + i % 3 for i in range(500)], "Region": ["North", "South"] * 250}).to_excel(path, index=False)
    df, types, errors, warnings = load.load_inputs([path])
    assert len(df) == 500 and types["Qty"] == "number" and types["Region"] == "text" and not errors


def test_the_unpacked_ceiling_leaves_room_for_the_biggest_sheet_the_pane_can_send():
    # 2,000,000 cells is the most the pane ever sends in one scan, and a sheet that size measures about 200 MB of cell
    # XML and shared strings: the ceiling must sit well above it, or an honest big sheet would be refused
    assert server.MAX_CELLS == 2_000_000
    assert load.MAX_UNPACKED >= server.MAX_CELLS * 100


# ---------------------------------------------------------------- 3. /fix's start_row

def _fix_body(start_row):
    return {"columns": ["Id", "Qty"], "rows": [["A1", "3"]], "row_index": 0, "start_row": start_row, "start_col": 0}


def test_the_sheets_last_row_is_a_fine_start_row_for_a_fix_and_one_past_it_is_a_clear_400(monkeypatch):
    # AH-185: /scan bounds start_row at EXCEL_ROWS and /fix did not, so any whole number went through to the AI call.
    # Fail-closed downstream (_in_table rejects every change), but the field is checked at the boundary like every other
    monkeypatch.setattr(client, "api_key_configured", lambda: True)
    monkeypatch.setattr(client, "suggest_fix", lambda *a, **k: {"explanation": "nothing to change", "changes": []})
    c = server.create_app().test_client()
    inside = c.post("/fix", json=_fix_body(server.EXCEL_ROWS - 1))
    assert inside.status_code == 200, inside.get_json()
    past = c.post("/fix", json=_fix_body(server.EXCEL_ROWS))
    assert past.status_code == 400
    assert past.get_json()["error"] == "'row_index', 'start_row', 'start_col' must be whole numbers inside the sheet"


# ---------------------------------------------------------------- 4. an invite kit's invite-code.txt

def _kit(tmp_path, text):
    kit = tmp_path / "kit"
    kit.mkdir(exist_ok=True)
    # newline="": without it Windows translates every "\n" on the way out, so a test asking for CRLF got "\r\r\n"
    # on disk and a byte comparison failed on correct code. A kit's file must land exactly as the test spells it.
    (kit / "invite-code.txt").write_text(text, encoding="utf-8", newline="")
    return kit / "Arcas.exe"


@pytest.mark.parametrize("text", ["", "   ", "not a code at all", "inv_short", "inv_" + "a" * 19, "inv_" + "a" * 65,
                                  "inv_" + "a" * 24 + " and then some words",
                                  "inv_aaaaaaaaaaaaaaaaaaaa!!",  # gitleaks:allow - made-up, and the only one spelled
                                  # out in full here: every other case is built by concatenation, which tools/
                                  # secret_history.py cannot match in the source and so never reports
                                  "x" * 5000,
                                  "inv_" + "a" * 24 + "\nAIzaSomethingElse"],
                         ids=["empty", "spaces", "words", "too short", "one short of 20", "one past 64", "a code and more",
                              "a character the shape forbids", "a long blob", "two lines"])
def test_an_invite_kit_whose_code_file_is_not_a_whole_invite_code_saves_nothing(monkeypatch, tmp_path, text):
    # AH-185: whatever invite-code.txt held was sealed into %LOCALAPPDATA% unread, while a pasted code goes through
    # server.INVITE_CODE. Worst case was a 401 from the relay, but the check already existed one function away.
    sealed_mod = _fake_dpapi(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    good = "inv_" + "g" * 24
    sealed_mod.save(home / "invite-code.txt", good)  # a code saved before: a bad kit must not touch it
    app.keep_invite(_kit(tmp_path, text), home)
    assert sealed_mod.read(home / "invite-code.txt") == good, text
    (home / "invite-code.txt").unlink()
    app.keep_invite(_kit(tmp_path, text), home)
    assert not (home / "invite-code.txt").exists(), text


def test_an_invite_kit_whose_code_file_holds_a_whole_invite_code_is_still_sealed_as_before(monkeypatch, tmp_path):
    # the other way round: John's own kits keep working, and the kit is left exactly as he made it
    sealed_mod = _fake_dpapi(monkeypatch)
    home = tmp_path / "home"
    home.mkdir()
    code = "inv_" + "h" * 24
    me = _kit(tmp_path, code + "\r\n")
    app.keep_invite(me, home)
    assert (home / "invite-code.txt").read_bytes().startswith(sealed.PREFIX)
    assert sealed_mod.read(home / "invite-code.txt") == code
    # read as BYTES, never read_text(): universal newlines translate the CRLF written above back to a bare newline,
    # so the assertion failed on a file that is byte-for-byte correct. Fourth newline-translation false failure found
    # on 2026-11-17 (AH-186). The claim here is that the kit's own file is left untouched, so compare the bytes.
    assert me.with_name("invite-code.txt").read_bytes() == (code + "\r\n").encode()
