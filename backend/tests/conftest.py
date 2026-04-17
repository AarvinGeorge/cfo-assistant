"""
conftest.py

Shared pytest configuration that makes the backend package importable for all test modules.

Role in project:
    Test suite — provides session-level path setup so every test file can import
    from `backend.*` without installing the package. Run with:
    pytest tests/ -v

Coverage:
    - Inserts the repository root (three levels above this file) onto sys.path
    - Ensures `from backend.x import y` resolves correctly across the whole test suite
    - No fixtures are defined here; path munging is the sole responsibility
"""

import sys
from pathlib import Path

# Add backend's parent to sys.path so `from backend.x import y` works
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
