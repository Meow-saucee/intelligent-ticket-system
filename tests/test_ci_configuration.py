from pathlib import Path
import unittest


class CIConfigurationTests(unittest.TestCase):
    def test_ci_covers_supported_platforms_without_real_ai(self):
        path = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"
        workflow = path.read_text(encoding="utf-8")
        for expected in (
            "push:",
            "pull_request:",
            "branches: [main]",
            "permissions:",
            "contents: read",
            "actions/checkout@v7",
            "actions/setup-python@v7",
            "ubuntu-latest",
            "windows-latest",
            '"3.11"',
            '"3.12"',
            '"3.13"',
            '"3.14"',
            "python -m pip install .",
            "python -m unittest discover -s tests -v",
            "python -m compileall -q src tests",
            'AI_API_KEY: ""',
            'AI_MODEL: ""',
            'AI_BASE_URL: ""',
            "if: runner.os == 'Windows' && matrix.python-version == '3.14'",
            "if: runner.os == 'Linux' && matrix.python-version == '3.14'",
            "./scripts/demo.ps1",
            "bash scripts/demo.sh",
        ):
            self.assertIn(expected, workflow)
        self.assertNotIn("AI_TIMEOUT:", workflow)


if __name__ == "__main__":
    unittest.main()
