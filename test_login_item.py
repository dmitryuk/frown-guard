import os
import plistlib
import tempfile
import unittest
from unittest import mock

from frown_guard import login_item


class TestLaunchAtLogin(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        agent = os.path.join(self._tmp.name, "LaunchAgents", f"{login_item.LABEL}.plist")
        log = os.path.join(self._tmp.name, "Logs", "Frown Guard.log")
        self._patches = [
            mock.patch.object(login_item, "AGENT_PATH", agent),
            mock.patch.object(login_item, "LOG_PATH", log),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def test_not_supported_when_running_from_source(self) -> None:
        self.assertFalse(login_item.is_supported())
        with self.assertRaises(RuntimeError):
            login_item.enable()
        self.assertFalse(login_item.is_enabled())

    def test_enable_writes_supervised_background_agent(self) -> None:
        exe = "/Applications/Frown Guard.app/Contents/MacOS/Frown Guard"
        with mock.patch.object(login_item, "app_executable", return_value=exe):
            login_item.enable()
        self.assertTrue(login_item.is_enabled())
        with open(login_item.AGENT_PATH, "rb") as f:
            agent = plistlib.load(f)
        self.assertEqual(agent["Label"], login_item.LABEL)
        self.assertEqual(agent["ProgramArguments"], [exe, "--background"])
        self.assertTrue(agent["RunAtLoad"])
        # Restart after a crash, but not after the user quits (exit status 0)
        self.assertEqual(agent["KeepAlive"], {"SuccessfulExit": False})

        login_item.disable()
        self.assertFalse(login_item.is_enabled())
        login_item.disable()  # idempotent


if __name__ == "__main__":
    unittest.main()
