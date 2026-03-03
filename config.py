from __future__ import annotations
from pathlib import Path

# Project root directory (directory containing landing.py)
PROJECT_ROOT = Path(__file__).resolve().parent

def path_in_project(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)
