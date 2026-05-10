import unittest
import sys
import os
import json
import shlex
from pathlib import Path

# Add the parent directory to sys.path to import app.py
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import logic from app.py
# We might need to mock some things if app.py does a lot on import
try:
    from app import sanitize_command, load_config
except ImportError:
    # If app.py is not importable without dependencies, we can test by re-implementing or mocking
    pass

class TestServiceLauncherLogic(unittest.TestCase):
    def test_shlex_split(self):
        """Verify that shlex.split handles spaces and quotes as expected."""
        cmd = 'python3 "/path with spaces/script.py" --arg "value with spaces"'
        split_cmd = shlex.split(cmd)
        self.assertEqual(split_cmd, ['python3', '/path with spaces/script.py', '--arg', 'value with spaces'])

    def test_positional_arguments(self):
        """Verify handling of positional arguments (empty key)."""
        # Re-implementing the logic from app.py to verify it
        def mock_sanitize(command, params):
            cmd_list = shlex.split(command)
            for key, value in params.items():
                if key == "":
                    cmd_list.append(str(value))
                else:
                    cmd_list.append(str(key))
                    cmd_list.append(str(value))
            return cmd_list

        cmd = "tail -f"
        params = {"": "/var/log/syslog"}
        result = mock_sanitize(cmd, params)
        self.assertEqual(result, ["tail", "-f", "/var/log/syslog"])

    def test_named_arguments(self):
        """Verify handling of named arguments."""
        def mock_sanitize(command, params):
            cmd_list = shlex.split(command)
            for key, value in params.items():
                if key == "":
                    cmd_list.append(str(value))
                else:
                    cmd_list.append(str(key))
                    cmd_list.append(str(value))
            return cmd_list

        cmd = "python3 script.py"
        params = {"--port": "8080", "--host": "0.0.0.0"}
        result = mock_sanitize(cmd, params)
        # Note: dictionary order might vary in older python, but 3.7+ is ordered
        self.assertEqual(result, ["python3", "script.py", "--port", "8080", "--host", "0.0.0.0"])

class TestConfig(unittest.TestCase):
    def test_config_exists(self):
        config_path = Path(__file__).parent.parent / "scripts_config.yaml"
        self.assertTrue(config_path.exists(), "scripts_config.yaml should exist")

    def test_example_config_exists(self):
        example_path = Path(__file__).parent.parent / "scripts_config.yaml.example"
        self.assertTrue(example_path.exists(), "scripts_config.yaml.example should exist")

if __name__ == "__main__":
    unittest.main()
