from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def _ensure_frontend_dist():
    """Create minimal frontend/dist/index.html for SPA catch-all tests."""
    dist_dir = Path(__file__).parent.parent / "frontend" / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    index = dist_dir / "index.html"
    created = not index.exists()
    if created:
        index.write_text(
            "<!DOCTYPE html><html><head><title>docsfy</title></head>"
            "<body><div id='root'></div></body></html>"
        )
    yield
    if created:
        index.unlink(missing_ok=True)
