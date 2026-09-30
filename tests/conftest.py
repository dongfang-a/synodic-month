from pathlib import Path

import pytest
from skyfield.api import load_file

from synodic.time_data import TimeData

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def time_data():
    return TimeData.read(ROOT / "data/leap-seconds.list")


@pytest.fixture(scope="session")
def eph():
    path = ROOT / "data/de440s.bsp"
    if not path.exists():
        pytest.fail("Run python -m synodic prepare before the integration tests.")
    kernel = load_file(str(path))
    yield kernel
    kernel.close()
