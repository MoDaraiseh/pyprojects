"""Make each project folder importable and keep every test away from real data."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # also allow `import recommender.recommend`
for folder in ("automation", "budget_tracker", "recommender", "web_scraper", "app_clone"):
    sys.path.insert(0, str(ROOT / folder))

# app.py creates its database at import time; point it at a throwaway file first.
os.environ["SNIP_DB"] = str(Path(tempfile.mkdtemp(prefix="snip-test-")) / "snip.db")
os.environ.pop("BUDGET_DB", None)
