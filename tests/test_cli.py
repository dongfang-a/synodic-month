import csv
import json
from pathlib import Path

from synodic.cli import main, sha256

ROOT = Path(__file__).resolve().parents[1]


def test_cli_exports_and_protects_existing_files(tmp_path):
    args = ["calculate", "--start", "2024-04-01", "--end", "2024-05-01",
            "--kernel", str(ROOT / "data/de440s.bsp"), "--leaps", str(ROOT / "data/leap-seconds.list"),
            "--out", str(tmp_path)]
    assert main(args) == 0
    data = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert [e["phase"] for e in data["events"]] == ["new", "full"]
    assert len(data["lunations"]) == 1
    assert data["lunations"][0]["next_new_inside_requested_interval"] is False
    with (tmp_path / "events.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2 and rows[0]["phase_zh"] == "朔"
    assert rows[0]["utc"] == data["events"][0]["utc"]
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["output_sha256"].items():
        assert sha256(tmp_path / name) == expected
    assert main(args) == 2


def test_empty_csv_still_has_headers(tmp_path):
    assert main(["calculate", "--start", "2024-01-01", "--end", "2024-01-02", "--out", str(tmp_path),
                 "--kernel", str(ROOT / "data/de440s.bsp"), "--leaps", str(ROOT / "data/leap-seconds.list")]) == 0
    with (tmp_path / "lunations.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames and list(reader) == []


def test_future_utc_boundary_rejected(tmp_path):
    assert main(["calculate", "--start", "2125-01-01", "--end", "2126-01-01", "--boundary-scale", "utc",
                 "--leaps", str(ROOT / "data/leap-seconds.list"), "--out", str(tmp_path)]) == 2
