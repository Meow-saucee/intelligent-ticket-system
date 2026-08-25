import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
TEST_RESULTS = ROOT / "docs" / "test-results.md"
RELEASE_PLAN = ROOT / "docs" / "development" / "2026-08-24-open-source-release-plan.md"
PUBLIC_TEXT_FILES = (
    README,
    ROOT / "CONTRIBUTING.md",
    ROOT / "SECURITY.md",
    *sorted((ROOT / "docs").rglob("*.md")),
    *sorted((ROOT / "evaluation" / "results").rglob("*.json")),
)

MANDATORY_README_LOCAL_TARGETS = {
    "LICENSE",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/设计与协作说明.md",
    "docs/验收演示步骤.md",
    "docs/test-results.md",
    "docs/development/2026-08-08-system-design.md",
    "docs/development/2026-08-08-implementation-plan.md",
    "docs/development/2026-08-24-open-source-release-design.md",
    "docs/development/2026-08-24-open-source-release-plan.md",
    "evaluation/cases.json",
    "evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json",
    "evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json",
}

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
MARKDOWN_IMAGE = re.compile(r"!\[[^]]*\]\(")
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
    def test_contributing_powershell_activation_uses_current_directory_prefix(self):
        self.assertIn(
            ".\\.venv\\Scripts\\Activate.ps1",
            _read(ROOT / "CONTRIBUTING.md"),
        )

    def test_release_plan_removes_accidental_task_4_report_from_public_history(self):
        plan = _read(RELEASE_PLAN)
        self.assertIn("--path .superpowers/sdd/task-4-report.md", plan)
        self.assertIn(
            "deleting only `findings.md`, `progress.md`, `task_plan.md`, and "
            "`.superpowers/sdd/task-4-report.md`",
            plan,
        )

    def test_release_plan_scopes_public_history_to_main_and_preserves_host_refs(self):
        plan = _read(RELEASE_PLAN)
        self.assertIn("public release scope is exactly `refs/heads/main`", plan)
        self.assertIn("preserve all `refs/codex/**` refs unchanged", plan)
        self.assertIn("record each local Codex ref's object ID and object type separately", plan)
        self.assertIn("reachable from `refs/heads/main`", plan)
        self.assertIn("excluded from the exact outgoing refspec", plan)
        self.assertIn("git bundle create $bundle --all", plan)
        self.assertIn("git push -u origin main", plan)
        self.assertIn("never use `--all` or `--mirror`", plan)

    def test_release_plan_proves_archive_import_comes_from_fresh_venv(self):
        plan = _read(RELEASE_PLAN)
        self.assertIn("Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue", plan)
        self.assertIn("archive import origin", plan)
        self.assertIn("site-packages", plan)

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

    def test_readme_has_exactly_three_badge_images(self):
        self.assertEqual(len(MARKDOWN_IMAGE.findall(_read(README))), 3)

    def test_readme_links_every_mandatory_public_target(self):
        linked_targets = set(_local_link_targets(_read(README)))
        self.assertEqual(len(MANDATORY_README_LOCAL_TARGETS), 13)
        self.assertTrue(
            MANDATORY_README_LOCAL_TARGETS.issubset(linked_targets),
            MANDATORY_README_LOCAL_TARGETS - linked_targets,
        )

    def test_quick_starts_do_not_use_placeholder_ticket_ids(self):
        self.assertNotIn("TKT-YYYYMMDD", _read(README))

    def test_powershell_quick_start_derives_alice_ticket_id(self):
        readme = _read(README)
        commands = (
            "$SeedTickets = @(ticket-system --db data/tickets.db list --submitter alice | ConvertFrom-Json)",
            "$TicketId = $SeedTickets[0].public_id",
            "ticket-system --db data/tickets.db show $TicketId --history",
        )
        positions = [readme.find(command) for command in commands]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))

    def test_posix_quick_start_derives_alice_ticket_id_without_jq(self):
        readme = _read(README)
        assignment = (
            'TICKET_ID="$(ticket-system --db data/tickets.db list --submitter alice | '
            "python -c 'import json, sys; print(json.load(sys.stdin)[0][\"public_id\"])')"
            '"'
        )
        show = 'ticket-system --db data/tickets.db show "$TICKET_ID" --history'
        self.assertIn(assignment, readme)
        self.assertIn(show, readme)
        self.assertLess(readme.find(assignment), readme.find(show))
        self.assertNotIn("jq", readme)

    def test_readme_explains_all_review_actions_accurately(self):
        readme = _read(README)
        for contract in (
            "`confirm` 默认采用原建议，也可以同时提供分类和优先级作为成对覆盖；建议状态记录为 `confirmed`。",
            "`modify` 必须同时提供最终分类和优先级，建议状态记录为 `modified`。",
            "`reject` 不改变工单内容、状态、分类、优先级或版本。",
            "D -->|confirm| E[按原建议或成对覆盖更新工单]",
        ):
            with self.subTest(contract=contract):
                self.assertIn(contract, readme)

    def test_readme_avoids_overclaims_and_personal_paths(self):
        readme = _read(README)
        for claim in ("企业级", "生产就绪"):
            with self.subTest(claim=claim):
                self.assertNotIn(claim, readme)
        self.assertNotIn(Path.home().name, readme)
        self.assertIsNone(WINDOWS_USERS_PATH.search(readme))

    def test_public_documentation_avoids_windows_user_directories(self):
        for path in PUBLIC_TEXT_FILES:
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
