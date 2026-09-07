import os
import pytest


@pytest.fixture(scope="session")
def base_url():
    """Viewer under test. Set VIEWER_URL in CI/compose; localhost for manual runs."""
    return os.environ.get("VIEWER_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    # tests run as root inside the container -> chromium needs --no-sandbox
    return {**browser_type_launch_args, "args": ["--no-sandbox"]}
