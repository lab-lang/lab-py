import tempfile

import pytest


def pytest_configure(config):
    """Isolate robot configuration before collection imports the offline simulator."""
    directory = tempfile.TemporaryDirectory(prefix="lab-compiler-opentrons-")
    config.add_cleanup(directory.cleanup)
    environment = pytest.MonkeyPatch()
    config.add_cleanup(environment.undo)
    environment.setenv("OT_API_CONFIG_DIR", directory.name)
