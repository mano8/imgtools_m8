"""Shared pytest fixtures for imgtools_m8 tests."""

import os

import pytest

SOURCE_DIR = os.path.join(os.path.dirname(__file__), "sources_test")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output_test")


@pytest.fixture(autouse=True)
def ensure_output_dir():
    """Create output directory before each test and leave it after."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    yield


@pytest.fixture
def sources_path() -> str:
    """Absolute path to the test source images directory."""
    return SOURCE_DIR


@pytest.fixture
def output_path() -> str:
    """Absolute path to the test output directory."""
    return OUTPUT_DIR
