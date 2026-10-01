import os
import tempfile

from settings import PREFERENCES_ENV, ROBOT_CONFIG_CACHE_ENV

# The link loads the last robot's config from disk as soon as it is imported.
# Point that at a throwaway location before any test imports it, so the tests
# neither read nor overwrite the config cached by a real session on this machine.
_TEST_DIR = tempfile.mkdtemp(prefix="hexapod-link-tests-")
os.environ[ROBOT_CONFIG_CACHE_ENV] = os.path.join(_TEST_DIR, "robot_config.json")
# Likewise for the saved UI preferences (theme).
os.environ[PREFERENCES_ENV] = os.path.join(_TEST_DIR, "preferences.json")
