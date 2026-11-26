import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.config import get_settings

BASE_DIR = Path(__file__).resolve().parent.parent


class TestDeploymentAssets(unittest.TestCase):
    def test_deployment_files_exist(self) -> None:
        self.assertTrue((BASE_DIR / "deploy" / "oracle_setup.sh").is_file())
        self.assertTrue((BASE_DIR / "deploy" / "oracle-chat.service").is_file())
        self.assertTrue((BASE_DIR / "deploy" / "DEPLOYMENT.md").is_file())

    def test_setup_script_bash_syntax_is_valid(self) -> None:
        result = subprocess.run(
            ["bash", "-n", str(BASE_DIR / "deploy" / "oracle_setup.sh")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)

    def test_systemd_template_contains_required_placeholders(self) -> None:
        unit_text = (BASE_DIR / "deploy" / "oracle-chat.service").read_text(encoding="utf-8")
        self.assertIn("__APP_USER__", unit_text)
        self.assertIn("__APP_DIR__", unit_text)
        self.assertIn("__APP_PORT__", unit_text)
        self.assertIn("backend.main:app", unit_text)

    def test_ollama_timeout_env_override(self) -> None:
        with patch.dict(os.environ, {"OLLAMA_TIMEOUT": "420"}):
            settings = get_settings()
        self.assertEqual(settings.ollama_timeout, 420.0)


if __name__ == "__main__":
    unittest.main()
