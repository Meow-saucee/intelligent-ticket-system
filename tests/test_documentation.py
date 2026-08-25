import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TEST_RESULTS = ROOT / "docs" / "test-results.md"

APPROVED_OPENING = """# 智能工单协同系统

Local-first Python CLI ticket system with SQLite persistence, human-reviewed AI triage, audit trails, and prompt-injection evaluation.

[![CI](https://github.com/Meow-saucee/intelligent-ticket-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Meow-saucee/intelligent-ticket-system/actions/workflows/ci.yml)
[![Python 3.11–3.14](https://img.shields.io/badge/Python-3.11%E2%80%933.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
"""

REQUIRED_HEADINGS = (
    "# 智能工单协同系统",
    "Local-first Python CLI ticket system with SQLite persistence, human-reviewed AI triage, audit trails, and prompt-injection evaluation.",
    "## 核心能力",
    "## 工作流程",
    "## 快速开始",
    "## AI 配置与数据边界",
    "## 测试与评测",
    "## 项目结构",
    "## 已知限制",
    "## 相关文档",
    "## 贡献",
    "## 许可证与 AI 协作",
)

MARKDOWN_LINK = re.compile(r"\]\(([^)]+)\)")
WINDOWS_USERS_PATH = re.compile(r"(?i)(?<![A-Za-z])[A-Za-z]:[\\/]+Users(?:[\\/]+|\b)")


def _read(path):
    return path.read_text(encoding="utf-8")


def _local_link_targets(markdown):
    for raw_target in MARKDOWN_LINK.findall(markdown):
        target = raw_target.strip()
        if target.startswith("<") and ">" in target:
            target = target[1:target.index(">")]
        else:
            target = target.split(maxsplit=1)[0]
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        yield unquote(parsed.path)


class DocumentationContractTests(unittest.TestCase):
    def test_readme_uses_approved_opening_and_badges(self):
        self.assertTrue(_read(README).startswith(APPROVED_OPENING))

    def test_readme_sections_appear_in_approved_order(self):
        readme = _read(README)
        positions = [readme.find(item) for item in REQUIRED_HEADINGS]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))

    def test_readme_contains_ci_workflow_and_mermaid_diagram(self):
        readme = _read(README)
        self.assertIn(
            "https://github.com/Meow-saucee/intelligent-ticket-system/actions/workflows/ci.yml",
            readme,
        )
        self.assertIn("```mermaid", readme)

    def test_readme_avoids_overclaims_and_personal_paths(self):
        readme = _read(README)
        for claim in ("企业级", "生产就绪"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, readme)
        self.assertNotIn(Path.home().name, readme)
        self.assertIsNone(WINDOWS_USERS_PATH.search(readme))

    def test_public_documentation_avoids_windows_user_directories(self):
        for path in (README, TEST_RESULTS):
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertIsNone(WINDOWS_USERS_PATH.search(_read(path)))

    def test_readme_relative_links_resolve(self):
        self._assert_relative_links_resolve(README)

    def test_test_results_relative_links_resolve(self):
        self._assert_relative_links_resolve(TEST_RESULTS)

    def _assert_relative_links_resolve(self, document):
        for target in _local_link_targets(_read(document)):
            with self.subTest(document=document.relative_to(ROOT), target=target):
                self.assertTrue((document.parent / target).exists(), target)


if __name__ == "__main__":
    unittest.main()
