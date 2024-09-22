"""Custom configurations for PyTest"""

# Package dependencies
import pytest


def pytest_addoption(parser):
    """Add the `--requires-hardware` option for running all normal tests plus tests that are marked
    with `@pytest.mark.requires_hardware`
    """
    parser.addoption(
        "--requires-hardware",
        action="store_true",
        default=False,
        help="Run tests with hardware connected",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_hardware: Mark test as requiring hardware")


def pytest_collection_modifyitems(config, items):
    """Handles testing for the `--requires-hardware` option"""

    # --requires-hardware given in CLI, so run all tests requiring hardware by returning early
    if config.getoption("--requires-hardware"):
        return None

    # Otherwise, skip all the tests requiring hardware
    skip_requires_hardware = pytest.mark.skip(reason="needs --requires-hardware option to run")
    for item in items:
        if "requires_hardware" in item.keywords:
            item.add_marker(skip_requires_hardware)
