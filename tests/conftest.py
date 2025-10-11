"""Pytest configuration for ndevio tests."""

from pathlib import Path

import pytest


@pytest.fixture
def resources_dir() -> Path:
    """Return path to test resources directory."""
    return Path(__file__).parent / "resources"
