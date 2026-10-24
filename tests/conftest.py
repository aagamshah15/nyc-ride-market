import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    """Point NYC_DATA_DIR at a temp folder so no test touches real pipeline data."""
    path = tmp_path / "data"
    path.mkdir()
    path = path.resolve()
    monkeypatch.setenv("NYC_DATA_DIR", str(path))
    return path
