"""AH-186: a Windows checkout (core.autocrlf=true, GitHub's Windows runners too) wrote every file .gitattributes left
unspecified with CRLF, so tools/test_site.mjs found none of contact.yml's field ids and the website layer was red for a
false reason (mutations.json the same day, AH-189). Every tracked text file now checks out LF, install.bat CRLF."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
KEEP_BYTES = "docs/airlock/chaos_dataset.csv"  # the Chaos Dataset is scored byte for byte, its CRLF included


def eol():
    """{path: (index eol, attributes)} as `git ls-files --eol` reads them."""
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("no git checkout here (an exe build or a source archive): nothing is checked out")
    out = subprocess.run(["git", "ls-files", "--eol", "-z"], cwd=ROOT, capture_output=True, check=True).stdout  # noqa: S603, S607
    files = {}
    for rec in filter(None, out.decode("utf-8").split("\0")):
        info, path = rec.split("\t", 1)
        files[path] = (info.split()[0], info[info.index("attr/") + 5:].split())
    return files


def test_every_tracked_text_file_checks_out_with_lf_on_a_windows_pc():
    wrong = []
    for path, (index, attr) in eol().items():
        if index == "i/-text" or path == KEEP_BYTES:
            continue
        want = "eol=crlf" if path.endswith(".bat") else "eol=lf"
        if want not in attr or index not in ("i/lf", "i/none"):
            wrong.append(f"{path}: {index} attr/{' '.join(attr)} (want i/lf and {want})")
    assert not wrong, "These would not check out as they are read on a core.autocrlf=true PC:\n" + "\n".join(wrong)


def test_install_bat_keeps_crlf_for_cmd_and_the_files_read_line_by_line_keep_lf():
    files = eol()
    assert "eol=crlf" in files["install.bat"][1]
    for path in (".github/ISSUE_TEMPLATE/contact.yml", "tools/mutations.json", "tools/test_site.mjs"):
        assert files[path] == ("i/lf", ["text=auto", "eol=lf"]), path
    assert files[KEEP_BYTES][1] == ["-text"]
