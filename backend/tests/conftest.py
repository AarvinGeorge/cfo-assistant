import sys
from pathlib import Path

# Add backend's parent to sys.path so `from backend.x import y` works
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
