import os
from pathlib import Path
import sys

# This product is local-only. Ultralytics reads this flag before initializing
# its module-level ONLINE state; force it before any model backend can import.
os.environ["YOLO_OFFLINE"] = "true"

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
