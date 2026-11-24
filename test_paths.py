import os
import tempfile
import unittest
from unittest import mock

from frown_guard import paths


class TestConfigPaths(unittest.TestCase):
    """The config file must live in a per-user writable directory, independent of the working directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.home = os.path.join(self._tmp.name, "home")
        self.cwd = os.path.join(self._tmp.name, "cwd")
        os.makedirs(self.home)
        os.makedirs(self.cwd)
        env = {"HOME": self.home, "USERPROFILE": self.home,
               "APPDATA": os.path.join(self.home, "AppData"),
               "XDG_CONFIG_HOME": os.path.join(self.home, ".config")}
        self._env = mock.patch.dict(os.environ, env)
        self._env.start()
        self._old_cwd = os.getcwd()
        os.chdir(self.cwd)

    def tearDown(self) -> None:
        os.chdir(self._old_cwd)
        self._env.stop()
        self._tmp.cleanup()

    def test_config_file_is_absolute_and_under_home(self) -> None:
        path = paths.config_file()
        self.assertTrue(os.path.isabs(path))
        self.assertTrue(os.path.realpath(path).startswith(os.path.realpath(self.home)))
        self.assertEqual(os.path.basename(path), "config.json")
        self.assertTrue(os.path.isdir(os.path.dirname(path)))

    def test_legacy_config_in_working_directory_is_migrated_once(self) -> None:
        with open("config.json", "w", encoding="utf-8") as f:
            f.write('{"sensitivity": 1.5}')
        path = paths.config_file()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"sensitivity": 1.5}')

        # An existing per-user config is never overwritten by the legacy file
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"sensitivity": 2.0}')
        paths.config_file()
        with open(path, encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"sensitivity": 2.0}')


if __name__ == "__main__":
    unittest.main()
