import os
import tempfile

from settings import ROBOT_CONFIG_CACHE_ENV

# The link loads the last robot's config from disk as soon as it is imported.
# Point that at a throwaway location before any test imports it, so the tests
# neither read nor overwrite the config cached by a real session on this machine.
os.environ[ROBOT_CONFIG_CACHE_ENV] = os.path.join(
    tempfile.mkdtemp(prefix="hexapod-link-tests-"), "robot_config.json"
)
