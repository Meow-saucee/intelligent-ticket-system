# Open Source Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing ticket system as a credible MIT-licensed public GitHub project while preserving its small-step history, moving raw work notes to a private repository, and proving local/CI behavior without exposing credentials or workstation data.

**Architecture:** Implement and review all ordinary file changes on an isolated release worktree, with one focused commit per independently reviewable concern. Only after the complete local release candidate passes verification will the orchestrator create the private notes backup, rehearse history filtering in a fresh clone, apply the verified filter to the formal repository, and create/push the public repository through GitHub web plus Git Credential Manager.

**Tech Stack:** Python 3.11–3.14 standard library, `unittest`, SQLite 3.35+, PowerShell 5.1/7, Bash, Git 2.54+, temporary `git-filter-repo==2.47.0`, GitHub Actions, GitHub web UI, HTTPS/Git Credential Manager.

## Global Constraints

- Start execution by invoking `superpowers:using-git-worktrees`; create branch `codex/open-source-release` at `.worktrees/open-source-release` from the current HEAD that contains both the approved specification and this implementation plan.
- Do not copy the root workspace's modified `findings.md`, `progress.md`, `task_plan.md`, or untracked `HANDOFF.md` into the public implementation worktree.
- Keep the existing 47 tests green; every new behavior or release contract gets a failing test before implementation.
- Use repo-local author identity `Meow-saucee <116954433+Meow-saucee@users.noreply.github.com>` for all new commits; preserve all earlier Codex authors during filtering.
- Production runtime remains Python standard-library only; keep package name and console command `ticket-system`, version `0.1.0`, and `requires-python = ">=3.11"`.
- Never configure or call a real AI service in tests, CI, or demo verification. Clear `AI_API_KEY`, `AI_MODEL`, and `AI_BASE_URL` for offline gates; do not set `AI_TIMEOUT` to an empty string.
- Never print credential values, Authorization headers, full environment dumps, full raw model responses, or matched secret text. Secret scans may report only rule name, object ID, path, length, entropy, and a short hash fingerprint.
- Do not install GitHub CLI. Web/GCM failure is a stop condition unless the user separately approves another authentication method.
- Do not create either remote repository until Tasks 1–8 are committed and the local release candidate passes every gate.
- Use `apply_patch` for authored file changes. `git mv`, exact report export, Git filtering, line-ending normalization, and other bulk mechanical transformations may use their purpose-built tools.
- Before any recursive worktree removal, resolve and verify the exact absolute path is inside `.worktrees/`; do not delete the root workspace, the private notes clone, the bundle, or rehearsal clones.
- Before the first implementation commit, set and read back the repository-local identity `Meow-saucee <116954433+Meow-saucee@users.noreply.github.com>` and assert `HEAD:docs/superpowers/plans/2026-08-24-open-source-release.md` exists.
- Treat every native command as its own gate. When several native commands share a PowerShell block, capture `$LASTEXITCODE` immediately after each command and throw on any unexpected nonzero value; an expected no-match scan accepts only exit code `1` and reports paths only, never matching text.

---

### Task 1: Make the PowerShell demo fail fast

**Files:**
- Create: `tests/test_demo_script.py`
- Modify: `scripts/demo.ps1`

**Interfaces:**
- Consumes: existing `ticket_system` CLI exit codes `0`, `2`, `3`, and `4`.
- Produces: `Invoke-Python [string[]]$Arguments`, which passes stdout through unchanged and terminates the script with the exact native Python exit code on unexpected failure.

- [ ] **Step 1: Add the Windows-only failing regression test**

Create `tests/test_demo_script.py` with this complete test:

```python
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class DemoPowerShellTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "PowerShell demo regression is Windows-only")
    def test_unexpected_python_failure_stops_demo_immediately(self):
        engines = list(
            dict.fromkeys(
                path
                for name in ("powershell.exe", "pwsh.exe")
                if (path := shutil.which(name))
            )
        )
        if not engines:
            self.skipTest("PowerShell is unavailable")

        project_root = Path(__file__).resolve().parents[1]
        source_script = project_root / "scripts" / "demo.ps1"

        for engine in engines:
            with self.subTest(engine=engine), tempfile.TemporaryDirectory() as tempdir:
                temp = Path(tempdir)
                sandbox = temp / "project"
                scripts = sandbox / "scripts"
                scripts.mkdir(parents=True)
                (sandbox / "src").mkdir()
                copied_script = scripts / "demo.ps1"
                shutil.copyfile(source_script, copied_script)

                shim_dir = temp / "shim"
                shim_dir.mkdir()
                call_log = temp / "python-calls.txt"
                (shim_dir / "python.cmd").write_text(
                    '@echo off\n'
                    '>>"%DEMO_PYTHON_CALL_LOG%" echo called\n'
                    'exit /b 37\n',
                    encoding="ascii",
                )

                environment = os.environ.copy()
                environment["PATH"] = str(shim_dir) + os.pathsep + environment.get("PATH", "")
                environment["DEMO_PYTHON_CALL_LOG"] = str(call_log)
                pathext = environment.get("PATHEXT", "")
                if ".CMD" not in pathext.upper().split(os.pathsep):
                    environment["PATHEXT"] = ".CMD" + (os.pathsep + pathext if pathext else "")
                for name in ("AI_API_KEY", "AI_MODEL", "AI_BASE_URL"):
                    environment.pop(name, None)

                result = subprocess.run(
                    [
                        engine,
                        "-NoLogo",
                        "-NoProfile",
                        "-NonInteractive",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(copied_script),
                    ],
                    cwd=sandbox,
                    env=environment,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                diagnostic = f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
                self.assertEqual(result.returncode, 37, diagnostic)
                calls = call_log.read_text(encoding="ascii").splitlines() if call_log.exists() else []
                self.assertEqual(calls, ["called"], diagnostic)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the regression test and confirm RED**

Run:

```powershell
$env:PYTHONPATH = (Resolve-Path 'src').Path
python -m unittest tests.test_demo_script.DemoPowerShellTests.test_unexpected_python_failure_stops_demo_immediately -v
```

Expected: FAIL because the current script does not return sentinel `37` immediately and/or calls the shim more than once.

- [ ] **Step 3: Add the minimal cross-version wrapper and convert required-success calls**

Insert after the encoding/environment setup in `scripts/demo.ps1`:

```powershell
function Invoke-Python {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & python @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        exit $exitCode
    }
}
```

Replace every Python invocation that must succeed with `Invoke-Python`. For JSON results, capture and parse only after the wrapper returns, for example:

```powershell
$createdJson = Invoke-Python -m ticket_system --db $db create --title '演示 VPN' --description '无法连接公司网络' --submitter demo --priority P1
$created = $createdJson | ConvertFrom-Json
```

Apply the same `*Json` pattern to every JSON-producing call. Audit the full file: init, seed, create/show, the four legal status transitions, list, all optional-AI create/analyze/review/evaluate commands, unittest, and compileall must use `Invoke-Python`. Keep only the empty-title and duplicate commands as direct `python` calls; capture and validate each `$LASTEXITCODE` immediately before starting another command. Do not modify `scripts/demo.sh`, the CLI, source encoding, or user-visible success output.

- [ ] **Step 4: Run GREEN and the focused script checks**

Run:

```powershell
python -m unittest tests.test_demo_script -v
Remove-Item Env:AI_API_KEY,Env:AI_MODEL,Env:AI_BASE_URL -ErrorAction SilentlyContinue
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/demo.ps1
pwsh.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/demo.ps1
python -m compileall -q src tests
git diff --check
```

Expected: the regression passes in both available engines; both real offline demos and compile check exit `0`.

- [ ] **Step 5: Commit the focused fix**

```powershell
git add -- tests/test_demo_script.py scripts/demo.ps1
git diff --cached --check
git commit -m "fix: propagate PowerShell demo failures"
```

---

### Task 2: Add the MIT license, package metadata, and repository hygiene

**Files:**
- Create: `LICENSE`
- Create: `.gitattributes`
- Create: `tests/test_project_metadata.py`
- Modify: `pyproject.toml`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: existing package name, version, Python floor, and console entry point.
- Produces: complete PEP 621 project metadata and deterministic public ignore/line-ending policy without runtime dependencies.

- [ ] **Step 1: Add failing metadata tests**

Create `tests/test_project_metadata.py`:

```python
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProjectMetadataTests(unittest.TestCase):
    def test_pyproject_exposes_public_project_metadata(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(project["name"], "ticket-system")
        self.assertEqual(project["version"], "0.1.0")
        self.assertEqual(project["requires-python"], ">=3.11")
        self.assertEqual(project["dependencies"], [])
        self.assertEqual(project["license"], {"file": "LICENSE"})
        self.assertEqual(project["authors"], [{"name": "Meow-saucee"}])
        self.assertEqual(project["urls"]["Repository"], "https://github.com/Meow-saucee/intelligent-ticket-system")
        self.assertEqual(project["scripts"]["ticket-system"], "ticket_system.cli:main")

    def test_license_and_line_ending_policy_exist(self):
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Meow-saucee", license_text)
        attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
        self.assertIn("* text=auto eol=lf", attributes)
        self.assertIn("*.sh text eol=lf", attributes)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the tests and confirm RED**

Run `python -m unittest tests.test_project_metadata -v`.

Expected: ERROR/FAIL because `LICENSE`, `.gitattributes`, and required metadata are absent.

- [ ] **Step 3: Add the exact license and metadata**

Create `LICENSE` with the standard MIT text and this project-specific line:

```text
MIT License

Copyright (c) 2026 Meow-saucee

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Create `.gitattributes`:

```gitattributes
* text=auto eol=lf
*.sh text eol=lf
```

Extend `[project]` in `pyproject.toml` with the exact description, `readme = "README.md"`, `license = { file = "LICENSE" }`, author, keywords, Python 3.11–3.14 classifiers, console environment, MIT classifier, `Development Status :: 3 - Alpha`, and `Topic :: Office/Business`. Add:

```toml
[project.urls]
Homepage = "https://github.com/Meow-saucee/intelligent-ticket-system"
Repository = "https://github.com/Meow-saucee/intelligent-ticket-system"
Issues = "https://github.com/Meow-saucee/intelligent-ticket-system/issues"
Documentation = "https://github.com/Meow-saucee/intelligent-ticket-system#readme"
```

- [ ] **Step 4: Expand `.gitignore` without hiding example configuration**

Keep existing rules and add: `*.egg-info/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage.*`, `htmlcov/`, `build/`, `dist/`, `.env.*`, `!.env.example`, `!.env.*.example`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `.credentials/`, `credentials/`, `.secrets/`, `secrets/`, `/*.db`, `/*.db-*`, `*.sqlite*`, `/reports/`, `*.log`, `.vscode/`, `.idea/`, `.DS_Store`, and `Thumbs.db`. Preserve `.worktrees/` and `tmp/`.

- [ ] **Step 5: Verify metadata, ignore rules, and line endings**

```powershell
python -m unittest tests.test_project_metadata -v
foreach ($sample in @('sample.sqlite3', 'reports/sample.json', '.env.local', 'build/sample.whl')) {
    git check-ignore --no-index --quiet -- $sample
    if ($LASTEXITCODE -ne 0) { throw "Expected ignored path: $sample" }
}
git check-attr eol -- scripts/demo.sh scripts/demo.ps1 README.md
git ls-files --eol
git diff --check
```

Expected: tests pass; all four sample paths are reported ignored; `demo.sh`, `demo.ps1`, and Markdown resolve to `eol: lf`; this read-only check does not stage unrelated files.

- [ ] **Step 6: Commit**

```powershell
git add -- LICENSE .gitattributes .gitignore pyproject.toml tests/test_project_metadata.py
git diff --cached --check
git commit -m "chore: add MIT license and package metadata"
```

---

### Task 3: Add contribution and security policies

**Files:**
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`

**Interfaces:**
- Produces: public contribution and vulnerability-reporting contracts that never require a personal email address.

- [ ] **Step 1: Create `CONTRIBUTING.md`**

Write concise Chinese guidance containing the exact supported setup (`Python 3.11+`, venv, `python -m pip install -e .`), the full unittest and compile commands, small-scope commit expectations, and these rules:

```markdown
- 不得提交 API Key、Authorization 头、数据库、日志、未脱敏模型响应或本机绝对路径。
- 修改 Prompt、AI schema、模型客户端或评测逻辑时，必须同时提交固定样例集的测试或评测证据。
- CI 永远不使用真实模型密钥；真实在线结果只能按公开评测 schema 提交。
```

- [ ] **Step 2: Create `SECURITY.md`**

State that vulnerabilities must be reported through GitHub Security Advisories / “Report a vulnerability,” not public Issues. Explicitly document that SQLite is unencrypted, there is no authentication/authorization, actor/reviewer values are audit labels, leaked credentials must be revoked/rotated first, and the project makes no fixed response or remediation SLA.

- [ ] **Step 3: Verify and commit**

```powershell
rg -n "Security Advisories|不得提交|没有身份认证|SQLite" CONTRIBUTING.md SECURITY.md
git diff --check
git add -- CONTRIBUTING.md SECURITY.md
git commit -m "docs: add contribution and security policies"
```

---

### Task 4: Add the cross-platform GitHub Actions matrix

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `tests/test_ci_configuration.py`

**Interfaces:**
- Produces: offline CI across Windows/Ubuntu and Python 3.11–3.14, with demos on Python 3.14 only.

- [ ] **Step 1: Add a failing workflow contract test**

Create `tests/test_ci_configuration.py`:

```python
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
```

- [ ] **Step 2: Run RED**

Run `python -m unittest tests.test_ci_configuration -v`.

Expected: ERROR because `.github/workflows/ci.yml` does not exist.

- [ ] **Step 3: Create the complete workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read

jobs:
  test:
    name: ${{ matrix.os }} / Python ${{ matrix.python-version }}
    runs-on: ${{ matrix.os }}
    timeout-minutes: 15
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, windows-latest]
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    env:
      AI_API_KEY: ""
      AI_MODEL: ""
      AI_BASE_URL: ""
      PYTHONUTF8: "1"
      PIP_DISABLE_PIP_VERSION_CHECK: "1"
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install package
        run: python -m pip install .
      - name: Run tests
        run: python -m unittest discover -s tests -v
      - name: Compile sources
        run: python -m compileall -q src tests
      - name: Run Windows demo without AI
        if: runner.os == 'Windows' && matrix.python-version == '3.14'
        shell: pwsh
        run: ./scripts/demo.ps1
      - name: Run POSIX demo without AI
        if: runner.os == 'Linux' && matrix.python-version == '3.14'
        shell: bash
        run: bash scripts/demo.sh
```

- [ ] **Step 4: Run GREEN and commit**

```powershell
python -m unittest tests.test_ci_configuration -v
git diff --check
git add -- .github/workflows/ci.yml tests/test_ci_configuration.py
git commit -m "ci: test supported Python versions on Windows and Ubuntu"
```

---

### Task 5: Export and prove safe public evaluation snapshots

**Files:**
- Create: `scripts/export_public_evaluation_results.py`
- Create: `tests/test_public_evaluation_results.py`
- Create: `evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json`
- Create: `evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json`

**Interfaces:**
- Consumes: an existing evaluation JSON, an expected source SHA-256, and a public date.
- Produces: schema version `1` JSON containing only `schema_version`, `redacted_snapshot`, `date`, `model`, `temperature`, `prompt_version`, `case_file_sha256`, `cases`, and `aggregate`.

- [ ] **Step 1: Write failing exporter and checked-in snapshot tests**

The tests must import `build_public_snapshot` and assert: wrong source SHA raises `ValueError`; top, case, and aggregate keys are allowlisted; malformed failure histograms are rejected; missing success fields remain absent rather than becoming `null`; checked-in reports use case SHA `a0585df6df13e28e0bb0172022f78163935775cb682f052991564480d75b584c`; baseline is 12 `invalid_response` failures; hardened is 12 valid, category `1.0`, priority `11/12`, injection `2/2`. Recursively walk all dictionary keys and string values and reject `authorization`, `api_key`, `bearer`, `raw_response`, `headers`, `base_url`, or a Windows user-directory marker; do not rely only on searching serialized JSON.

Run `python -m unittest tests.test_public_evaluation_results -v` and confirm RED because the exporter and public files do not exist.

- [ ] **Step 2: Implement the allowlist exporter**

Implement these exact constants and function contracts in `scripts/export_public_evaluation_results.py`:

```python
TOP_LEVEL_KEYS = (
    "model",
    "temperature",
    "prompt_version",
    "case_file_sha256",
    "cases",
    "aggregate",
)
CASE_KEYS = (
    "id",
    "expected_category",
    "expected_priority",
    "category",
    "priority",
    "valid",
    "category_correct",
    "priority_correct",
    "injection_safe",
    "failure_code",
)
AGGREGATE_KEYS = (
    "total",
    "valid",
    "failures",
    "valid_structure_rate",
    "category_accuracy",
    "priority_accuracy",
    "injection_total",
    "injection_safe",
    "injection_resistance_rate",
    "degradation_rate",
    "failure_histogram",
)


def build_public_snapshot(source_bytes: bytes, expected_sha256: str, date: str) -> dict:
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"source SHA-256 mismatch: {actual}")
    source = json.loads(source_bytes.decode("utf-8"))
    public = {
        "schema_version": 1,
        "redacted_snapshot": True,
        "date": date,
        **{
            key: source[key]
            for key in TOP_LEVEL_KEYS
            if key not in {"cases", "aggregate"}
        },
        "cases": [
            {key: case[key] for key in CASE_KEYS if key in case}
            for case in source["cases"]
        ],
        "aggregate": {
            key: source["aggregate"][key]
            for key in AGGREGATE_KEYS
        },
    }
    return public
```

Validate that `failure_histogram` is a dictionary whose keys are stable lowercase underscore error codes and whose values are non-negative integers. Add an argparse CLI with required `--source`, `--output`, `--expected-sha256`, and `--date`; write UTF-8 JSON using `ensure_ascii=False`, `indent=2`, a final newline, a temporary file in the destination directory, and atomic `Path.replace`.

- [ ] **Step 3: Generate only the two locked snapshots**

Resolve the formal checkout because ignored source reports are not copied into linked worktrees, then verify both source hashes before export:

```powershell
$commonGitDir = git rev-parse --path-format=absolute --git-common-dir
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve common Git directory' }
$formalRoot = Split-Path $commonGitDir -Parent
$baselineSource = Join-Path $formalRoot 'tmp\kimi-reports\baseline\20260808T181231.347454+0000.json'
$hardenedSource = Join-Path $formalRoot 'tmp\kimi-reports\hardened-v3\20260808T181636.457888+0000.json'
$sources = @(
    @{ Path = $baselineSource; Hash = '8010dd8d0bc5ccc1895705face9025c91781ba5915a4c5c1b2c1f2fdbf3523a8'; Output = 'evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json' },
    @{ Path = $hardenedSource; Hash = '3a0b9a9ab6b87867ce378a3b247f5cd1af7cfb3192883ab789932874efda568d'; Output = 'evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json' }
)
foreach ($source in $sources) {
    if (-not (Test-Path -LiteralPath $source.Path -PathType Leaf)) { throw "Missing source report: $($source.Path)" }
    $actual = (Get-FileHash -LiteralPath $source.Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $source.Hash) { throw "Source report hash mismatch: $($source.Path)" }
    python scripts/export_public_evaluation_results.py --source $source.Path --output $source.Output --expected-sha256 $source.Hash --date 2026-08-09
    if ($LASTEXITCODE -ne 0) { throw "Evaluation export failed: $($source.Output)" }
}
```

- [ ] **Step 4: Recompute metrics and compare source/public semantics**

Complete the tests so aggregate metrics are recomputed from the public cases: structure and degradation use all 12 cases; category/priority accuracy use valid cases; injection rate uses cases containing `injection_safe`; failure histogram uses invalid cases. When the ignored source files exist, compare every allowlisted case field and the entire aggregate dictionary to its source report.

Run:

```powershell
python -m unittest tests.test_public_evaluation_results -v
python -m unittest tests.test_evaluation -v
git diff --check
```

Expected: all tests pass; public/source allowed fields and aggregate are identical.

- [ ] **Step 5: Commit**

```powershell
git add -- scripts/export_public_evaluation_results.py tests/test_public_evaluation_results.py evaluation/results/moonshot-v1-8k/2026-08-09-baseline.json evaluation/results/moonshot-v1-8k/2026-08-09-hardened.json
git commit -m "docs: publish verified AI evaluation snapshots"
```

---

### Task 6: Correct and organize public development documentation

**Files:**
- Move: `docs/superpowers/specs/2026-08-08-intelligent-ticket-system-design.md` → `docs/development/2026-08-08-system-design.md`
- Move: `docs/superpowers/plans/2026-08-08-intelligent-ticket-system.md` → `docs/development/2026-08-08-implementation-plan.md`
- Move: `docs/superpowers/specs/2026-08-24-open-source-release-design.md` → `docs/development/2026-08-24-open-source-release-design.md`
- Move: `docs/superpowers/plans/2026-08-24-open-source-release.md` → `docs/development/2026-08-24-open-source-release-plan.md`
- Modify: `docs/设计与协作说明.md`
- Modify: `docs/验收演示步骤.md`
- Modify: `docs/test-results.md`

**Interfaces:**
- Produces: portable public docs whose stable guarantees are separated from one historical model run.

- [ ] **Step 1: Move formal records mechanically**

Create the destination with `New-Item -ItemType Directory -Force -Path 'docs\development' | Out-Null`, then use `git mv` for the four exact mappings above. Add a banner to the 2026-08-08 implementation plan: `> 历史实施记录：当前用法、支持版本和安全边界以仓库根目录 README 为准。`

- [ ] **Step 2: Correct stale system-design interfaces**

In the moved 2026-08-08 design, replace nonexistent `TICKET_DB_PATH` with the documented `--db` option, replace `AI_TIMEOUT_SECONDS` with `AI_TIMEOUT`, and replace the nonexistent `demo` CLI subcommand with `scripts/demo.ps1` / `scripts/demo.sh`.

- [ ] **Step 3: Correct security and acceptance language**

In `docs/设计与协作说明.md`, change the risk label to `未经审核或重复审核导致建议错误生效`, and explicitly state that submitter/actor/reviewer are audit labels, not authenticated identities.

In `docs/验收演示步骤.md`, remove the personal `Set-Location` and state that commands run from the repository root; where a post-clone example is useful, use `Set-Location intelligent-ticket-system`. For live AI steps, state that `hardware/P2` is the 2026-08-09 snapshot target; the stable gate requires a valid `pending` output with both `category != account_access` and `priority != P0`. Update the test section to say the original 47 tests plus release tests must all pass rather than hardcoding a final total.

- [ ] **Step 4: Make test evidence internally consistent**

Update `docs/test-results.md` to distinguish offline automated tests from the separate real Moonshot snapshot, add the exact case SHA, link both public JSON files, define each metric denominator, and state that baseline's 0% represents 12 schema rejections (`invalid_response`), not 12 wrong classifications. Do not hardcode a public-history commit hash that will change during filtering.

- [ ] **Step 5: Verify and commit**

```powershell
$stalePaths = @(rg -l "TICKET_DB_PATH|AI_TIMEOUT_SECONDS|越权生效|不存在的 demo" docs)
$staleCode = $LASTEXITCODE
if ($staleCode -eq 0) { throw "Stale documentation found in: $($stalePaths -join ', ')" }
if ($staleCode -ne 1) { throw "Documentation scan failed: $staleCode" }
$localUser = Split-Path (Resolve-Path '~').Path -Leaf
$personalPaths = @(rg -l --fixed-strings -- $localUser docs)
$personalCode = $LASTEXITCODE
if ($personalCode -eq 0) { throw "Personal identifier found in: $($personalPaths -join ', ')" }
if ($personalCode -ne 1) { throw "Personal identifier scan failed: $personalCode" }
git diff --check
git add -- docs/development/2026-08-08-system-design.md docs/development/2026-08-08-implementation-plan.md docs/development/2026-08-24-open-source-release-design.md docs/development/2026-08-24-open-source-release-plan.md docs/设计与协作说明.md docs/验收演示步骤.md docs/test-results.md
git commit -m "docs: organize and correct development records"
```

Expected: the search returns no stale interface or personal-path matches; only formal records are under `docs/development/`.

---

### Task 7: Rebuild the public README and add documentation contracts

**Files:**
- Create: `tests/test_documentation.py`
- Modify: `README.md`

**Interfaces:**
- Produces: the GitHub landing page and a test that validates required sections, prohibited claims, local relative links, and personal-path removal.

- [ ] **Step 1: Add failing README/document-link tests**

Create `tests/test_documentation.py` that asserts README contains, in order, `# 智能工单协同系统`, the approved English sentence, `## 核心能力`, `## 工作流程`, `## 快速开始`, `## AI 配置与数据边界`, `## 测试与评测`, `## 项目结构`, `## 已知限制`, `## 相关文档`, `## 贡献`, and `## 许可证与 AI 协作`; contains the CI workflow URL and Mermaid fence; does not contain `企业级`, `生产就绪`, or the real local username; and resolves every non-HTTP/non-anchor Markdown link in README and `docs/test-results.md` relative to its containing file.

Run `python -m unittest tests.test_documentation -v` and confirm RED against the current README.

- [ ] **Step 2: Replace README with the approved information architecture**

Use this exact opening and badges:

```markdown
# 智能工单协同系统

Local-first Python CLI ticket system with SQLite persistence, human-reviewed AI triage, audit trails, and prompt-injection evaluation.

[![CI](https://github.com/Meow-saucee/intelligent-ticket-system/actions/workflows/ci.yml/badge.svg)](https://github.com/Meow-saucee/intelligent-ticket-system/actions/workflows/ci.yml)
[![Python 3.11–3.14](https://img.shields.io/badge/Python-3.11%E2%80%933.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
```

Describe only implemented capabilities. Add one Mermaid graph with no more than eight nodes: create/persist → AI analysis → pending suggestion → confirm/modify/reject → ticket update or unchanged → audit history. Add PowerShell and POSIX quick starts that clone the repository, create/activate `.venv`, run `python -m pip install .`, and use `ticket-system`; keep `PYTHONPATH=src` only in the contributor/testing section.

Include deterministic JSON output captured from the offline `init`/`seed`/`show --history` flow. Present the AI pending/review lifecycle as commands and the Mermaid flow, and link the two checked-in sanitized snapshots for real-model predictions; do not invent an uncaptured AI response or a web screenshot.

State all boundaries explicitly: SQLite 3.35+; title/description are sent to the configured AI provider; tickets/audit/raw model response are stored in unencrypted SQLite; submitter/actor/reviewer are audit labels; no auth, authorization, encryption, Web UI, HA, or production SLA; online model output can drift; the published Moonshot metrics are one 2026-08-09 snapshot over 12 fixed cases.

Link every public document under `docs/` and both public result JSONs. Close with contribution, MIT, and: `本项目由 Meow-saucee 主导，借助 Codex 协作完成，最初源自一次 AI Coding 任务。`

State exactly that the automated demos cover the core workflow, invalid input, duplicates, optional live AI, and tests; provider failures are covered by the acceptance document and automated HTTP/protocol tests, not by an automatic demo claim.

- [ ] **Step 3: Run GREEN and full documentation checks**

```powershell
python -m unittest tests.test_documentation -v
python -m unittest tests.test_project_metadata tests.test_public_evaluation_results -v
$localUser = Split-Path (Resolve-Path '~').Path -Leaf
$forbiddenPaths = @(rg -l "企业级|生产就绪" README.md docs evaluation/results)
$forbiddenCode = $LASTEXITCODE
if ($forbiddenCode -eq 0) { throw "Prohibited claim found in: $($forbiddenPaths -join ', ')" }
if ($forbiddenCode -ne 1) { throw "Claim scan failed: $forbiddenCode" }
$personalPaths = @(rg -l --fixed-strings -- $localUser README.md docs evaluation/results)
$personalCode = $LASTEXITCODE
if ($personalCode -eq 0) { throw "Personal identifier found in: $($personalPaths -join ', ')" }
if ($personalCode -ne 1) { throw "Personal identifier scan failed: $personalCode" }
git diff --check
```

Expected: tests pass; the final search returns no personal path or prohibited claim in public content.

- [ ] **Step 4: Commit**

```powershell
git add -- README.md tests/test_documentation.py
git commit -m "docs: rebuild the open source project homepage"
```

---

### Task 8: Verify the complete local release candidate

**Files:**
- No intended tracked changes.

**Interfaces:**
- Produces: recorded release-gate evidence before any GitHub mutation.

- [ ] **Step 1: Run the entire installed and source test suite**

```powershell
function Invoke-Gate {
    param([string]$Label, [scriptblock]$Action)
    & $Action
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "$Label failed with exit code $code" }
}

Remove-Item Env:AI_API_KEY,Env:AI_MODEL,Env:AI_BASE_URL -ErrorAction SilentlyContinue
$env:PYTHONPATH = (Resolve-Path 'src').Path
Invoke-Gate 'full tests' { python -m unittest discover -s tests -v }
Invoke-Gate 'compileall' { python -m compileall -q src tests }
Invoke-Gate 'editable install' { python -m pip install -e . }
Invoke-Gate 'installed entry point' { ticket-system --help }
```

Expected: original 47 and all new tests pass; compilation and installed entry point succeed.

- [ ] **Step 2: Run both offline demos**

```powershell
Invoke-Gate 'Windows PowerShell demo' { powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/demo.ps1 }
Invoke-Gate 'PowerShell 7 demo' { pwsh.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File scripts/demo.ps1 }
$bash = (Get-Command bash.exe -ErrorAction Stop).Source
Invoke-Gate 'POSIX demo' { & $bash scripts/demo.sh }
```

Expected: all three executions return `0`, skip real AI, and finish with the full test suite.

- [ ] **Step 3: Verify a clean archive install**

Create and verify an isolated archive install without reusing the editable environment:

```powershell
$repoRoot = (Resolve-Path '.').Path
$archiveRoot = Join-Path $repoRoot ('tmp\open-source-release\archive-check\' + [guid]::NewGuid().ToString('N'))
if (Test-Path -LiteralPath $archiveRoot) { throw "Archive target already exists: $archiveRoot" }
$tree = Join-Path $archiveRoot 'tree'
$zip = Join-Path $archiveRoot 'source.zip'
New-Item -ItemType Directory -Path $tree -Force | Out-Null
Invoke-Gate 'git archive' { git archive --format=zip --output=$zip HEAD }
Expand-Archive -LiteralPath $zip -DestinationPath $tree
$archiveVenv = Join-Path $archiveRoot 'venv'
Invoke-Gate 'archive venv' { python -m venv $archiveVenv }
$archivePython = Join-Path $archiveVenv 'Scripts\python.exe'
Push-Location $tree
try {
    Invoke-Gate 'archive install' { & $archivePython -m pip install . }
    Invoke-Gate 'archive entry point' { & (Join-Path $archiveVenv 'Scripts\ticket-system.exe') --help }
    Invoke-Gate 'archive tests' { & $archivePython -m unittest discover -s tests -v }
    Invoke-Gate 'archive compileall' { & $archivePython -m compileall -q src tests }
} finally {
    Pop-Location
}
```

- [ ] **Step 4: Run release hygiene gates**

```powershell
Invoke-Gate 'whitespace check' { git diff --check }
$dirty = @(git status --porcelain)
if ($LASTEXITCODE -ne 0) { throw 'git status failed' }
if ($dirty.Count -ne 0) { throw "Release worktree is dirty: $($dirty -join ', ')" }
git ls-files --eol
$secretPaths = @(git grep -l -I -E "(BEGIN (RSA|OPENSSH|EC) PRIVATE KEY|gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|Authorization:[[:space:]]*Bearer)" HEAD)
$secretCode = $LASTEXITCODE
if ($secretCode -eq 0) { throw "Credential pattern found in: $($secretPaths -join ', ')" }
if ($secretCode -ne 1) { throw "Credential scan failed: $secretCode" }
$localUser = Split-Path (Resolve-Path '~').Path -Leaf
$personalPaths = @(git grep -l --fixed-strings -- $localUser HEAD)
$personalCode = $LASTEXITCODE
if ($personalCode -eq 0) { throw "Personal identifier found in: $($personalPaths -join ', ')" }
if ($personalCode -ne 1) { throw "Personal identifier scan failed: $personalCode" }
```

Expected: implementation worktree is clean after the planned commits; secret-pattern search returns no credible secret and never emits matched text. Record current `HEAD`, dynamic `git rev-list --count HEAD`, discovered test count, Python/SQLite versions, archive-install result, and source/public report hashes in ignored `tmp/open-source-release/evidence/pre-filter-release.json` before external work.

---

### Task 9: Create and verify the private notes repository

**Files/State:**
- Source-only local files: root workspace `findings.md`, `progress.md`, `task_plan.md`.
- Temporary private clone: unique `tmp/open-source-release/notes-stage/` outside the implementation worktree.
- Remote creation: `Meow-saucee/intelligent-ticket-system-notes` (private).

**Interfaces:**
- Produces: a private `main` branch containing only the three note paths, five historical note-touching commits plus one private checkpoint commit.

- [ ] **Step 1: Freeze and fingerprint source state**

Resolve the formal checkout from the common Git directory. Require the fixed operation targets not to exist, record `HEAD`, refs, status, and SHA-256 for the three modified notes and `HANDOFF.md`, and confirm none is staged. Store paths and hashes—not file contents—in ignored `tmp/open-source-release/evidence/notes-source.json`:

```powershell
$commonGitDir = git rev-parse --path-format=absolute --git-common-dir
if ($LASTEXITCODE -ne 0) { throw 'Cannot resolve common Git directory' }
$formalRoot = Split-Path $commonGitDir -Parent
$opsRoot = Join-Path $formalRoot 'tmp\open-source-release'
$notesStage = Join-Path $opsRoot 'notes-stage'
$toolsVenv = Join-Path $opsRoot 'tools-venv'
foreach ($target in @($notesStage, $toolsVenv)) {
    if (Test-Path -LiteralPath $target) { throw "Operation target already exists: $target" }
}
$noteNames = @('findings.md', 'progress.md', 'task_plan.md')
$sourceHashes = [ordered]@{}
foreach ($name in $noteNames) {
    $path = Join-Path $formalRoot $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Missing note: $path" }
    $sourceHashes[$name] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}
$handoff = Join-Path $formalRoot 'HANDOFF.md'
if (-not (Test-Path -LiteralPath $handoff -PathType Leaf)) { throw 'HANDOFF.md is missing' }
$staged = @(git -C $formalRoot diff --cached --name-only -- findings.md progress.md task_plan.md HANDOFF.md)
if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect staged note paths' }
if ($staged.Count -ne 0) { throw "Private material is staged: $($staged -join ', ')" }
$evidenceDir = Join-Path $opsRoot 'evidence'
New-Item -ItemType Directory -Force -Path $evidenceDir | Out-Null
[ordered]@{
    formal_head = (git -C $formalRoot rev-parse HEAD)
    note_sha256 = $sourceHashes
    handoff_sha256 = (Get-FileHash -LiteralPath $handoff -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidenceDir 'notes-source.json') -Encoding utf8
```

- [ ] **Step 2: Install the filtering tool in an ignored temporary venv**

```powershell
python -m venv $toolsVenv
if ($LASTEXITCODE -ne 0) { throw 'Cannot create filtering venv' }
$filterPython = Join-Path $toolsVenv 'Scripts\python.exe'
& $filterPython -m pip install git-filter-repo==2.47.0
if ($LASTEXITCODE -ne 0) { throw 'Cannot install pinned git-filter-repo' }
& $filterPython -m git_filter_repo --version
if ($LASTEXITCODE -ne 0) { throw 'Cannot execute git-filter-repo' }
```

- [ ] **Step 3: Build the notes-only history**

Fresh-clone the exact verified release branch, filter to the three note paths, and create the private-only current checkpoint:

```powershell
git clone --no-local --single-branch --branch codex/open-source-release -- $formalRoot $notesStage
if ($LASTEXITCODE -ne 0) { throw 'Cannot create notes-stage clone' }
Push-Location $notesStage
try {
    & $filterPython -m git_filter_repo --path findings.md --path progress.md --path task_plan.md --prune-empty auto
    if ($LASTEXITCODE -ne 0) { throw 'Notes history filtering failed' }
    git branch -M main
    if ($LASTEXITCODE -ne 0) { throw 'Cannot rename notes branch' }
    foreach ($name in $noteNames) {
        Copy-Item -LiteralPath (Join-Path $formalRoot $name) -Destination (Join-Path $notesStage $name)
        $copied = (Get-FileHash -LiteralPath (Join-Path $notesStage $name) -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($copied -ne $sourceHashes[$name]) { throw "Copied note hash mismatch: $name" }
    }
    git config user.name 'Meow-saucee'
    git config user.email '116954433+Meow-saucee@users.noreply.github.com'
    git add -- findings.md progress.md task_plan.md
    git diff --cached --check
    if ($LASTEXITCODE -ne 0) { throw 'Private checkpoint diff check failed' }
    git commit -m 'docs: save private release checkpoint'
    if ($LASTEXITCODE -ne 0) { throw 'Private checkpoint commit failed' }
    $tracked = @(git ls-files | Sort-Object)
    if (($tracked -join "`n") -ne (($noteNames | Sort-Object) -join "`n")) { throw "Unexpected notes paths: $($tracked -join ', ')" }
    $count = [int](git rev-list --count HEAD)
    if ($LASTEXITCODE -ne 0 -or $count -ne 6) { throw "Unexpected notes history count: $count" }
} finally {
    Pop-Location
}
```

Expected: exactly `findings.md`, `progress.md`, and `task_plan.md`; expected history is five filtered commits plus one checkpoint. If dynamic history differs, inspect commit subjects and stop rather than accepting extra paths.

- [ ] **Step 4: Create the private remote through the logged-in GitHub web UI**

Invoke the Chrome/in-app browser skill, confirm the visible signed-in profile is `Meow-saucee`, create `intelligent-ticket-system-notes` as **Private**, and do not initialize README, License, or `.gitignore`.

- [ ] **Step 5: Push with native Git/GCM and verify privacy**

In `$notesStage`, add exact remote `https://github.com/Meow-saucee/intelligent-ticket-system-notes.git`, assert `git remote get-url origin` equals that string, and run only `git push -u origin main`. Complete browser OAuth/2FA if Git Credential Manager prompts. Fetch `origin main`, require local `HEAD == origin/main`, and verify the three working-file SHA-256 values still equal `notes-source.json`. Confirm while logged in that there are exactly three files and six commits; use a fresh private/incognito browser context with no GitHub cookies and require `404`/not found. Do not continue if anonymous access succeeds.

---

### Task 10: Rehearse and apply the public-history rewrite

**Files/State:**
- Local bundle: unique `tmp/open-source-release/backups/pre-public-rewrite.bundle`.
- Restore test clone: unique `tmp/open-source-release/backups/restore-check/`.
- Rehearsal clone: unique `tmp/open-source-release/public-rehearsal/`.
- Replace rules: ignored `tmp/open-source-release/replace-text.txt` containing exact backslash, slash, and JSON-escaped variants of the real user path mapped to `<project-directory>`.

**Interfaces:**
- Produces: formal `main` history with unchanged public commit topology/metadata, no raw note paths, and no personal directory in any reachable blob.

- [ ] **Step 1: Integrate the verified release branch safely**

Before discarding any working-copy note edit, require all four recovery conditions: `$notesStage` still exists; `git -C $notesStage fetch origin main` succeeds; local notes `HEAD` equals `origin/main`; and every private-checkpoint working-file SHA-256 equals `notes-source.json`. Also require the future bundle and restore-check targets to be absent so this run cannot silently reuse stale evidence. Add exactly `HANDOFF.md` to the formal repository's `.git/info/exclude` with `apply_patch`, then run:

```powershell
git -C $formalRoot restore --worktree --source=HEAD -- findings.md progress.md task_plan.md
if ($LASTEXITCODE -ne 0) { throw 'Cannot restore public working-copy notes after private backup' }
$remaining = @(git -C $formalRoot status --porcelain)
if ($LASTEXITCODE -ne 0 -or $remaining.Count -ne 0) { throw "Formal checkout is not clean: $($remaining -join ', ')" }
git -C $formalRoot merge --ff-only codex/open-source-release
if ($LASTEXITCODE -ne 0) { throw 'Release branch is not a fast-forward of the formal branch' }
```

For each exact approved path `.worktrees/implementation` and `.worktrees/open-source-release`, resolve it with `[IO.Path]::GetFullPath`, require it to start with the resolved `.worktrees` directory plus a separator, require the value to equal one of those two approved paths, and require `git -C <path> status --porcelain` to be empty. Then run `git -C $formalRoot worktree remove -- <exact-path>` without `--force` for each and finish with `git -C $formalRoot worktree prune`.

- [ ] **Step 2: Create and prove the recovery bundle**

Use fixed absent targets `$bundle = tmp/open-source-release/backups/pre-public-rewrite.bundle` and `$restoreCheck = tmp/open-source-release/backups/restore-check`. Record dynamic `N = git rev-list --count HEAD`, current HEAD, `git show-ref`, and `git log --format=raw --date=raw --all` under the ignored evidence directory. Create `git bundle create $bundle --all`, check its exit code, run `git bundle verify $bundle`, then `git clone --no-local -- $bundle $restoreCheck`. Require the restore clone's checked-out HEAD to equal the recorded HEAD, its current-branch commit count to equal `N`, its remote refs to contain both pre-rewrite local branches, and `git ls-tree -r --name-only HEAD` to contain all three note paths. The bundle and restore clone remain ignored/local and are never pushed or removed during this release.

- [ ] **Step 3: Rehearse the exact filter in a fresh clone**

Create UTF-8 `tmp/open-source-release/replace-text.txt` with exactly three `literal:...==><project-directory>` rules generated from the formal root: native backslash, slash, and JSON-escaped-backslash forms. Verify the file contains three distinct source expressions, does not contain a credential, and record its SHA-256. Create one ignored `run-public-filter.ps1` whose only variable inputs are repository path and a `-Force` switch; it checks the recorded rule hash, enters the target repository, and invokes the pinned module with these fixed arguments:

```text
--path findings.md
--path progress.md
--path task_plan.md
--invert-paths
--replace-text <verified-rules-file>
--prune-empty never
--replace-refs delete-no-add
```

Fresh-clone the formal repository to the absent `$rehearsal` path with `--no-local`, then run the helper without `-Force`. Do not use `--force` in the fresh rehearsal. Parse `.git/filter-repo/commit-map`: after its header, require exactly `N` mappings reachable from the release-candidate branch, no all-zero new commit IDs, and no deleted commits. Save the helper and rule hashes in release evidence; the formal run must use those same files unchanged.

- [ ] **Step 4: Prove rehearsal equivalence**

Create an ignored `verify_history_filter.py` and run it with the original formal repository, rehearsal repository, commit-map path, replacement-rules path, and expected count. For every mapped commit it must compare author/committer names and emails, raw timestamps, full commit message bytes, and parents translated through the commit map; compare complete trees after deleting only `findings.md`, `progress.md`, and `task_plan.md` and applying the three exact byte replacements to original blobs. It must fail on any other path/content/topology change.

The same verifier must enumerate all refs and reachable blobs in the rehearsal, reject `refs/original`, `refs/replace`, unexpected remotes, note paths, the real username/path variants, and credential patterns. On a match it may print only rule name, object ID, path, byte length, entropy (where applicable), and a 12-character SHA-256 fingerprint—never matched text. Then, in separate checked gates, run the full tests, compile, install, Windows PowerShell 5.1/7 demos, discovered `bash.exe` POSIX demo, public report tests, and `git diff --check` inside the rehearsal. Store the verifier source SHA-256 and results in ignored evidence.

- [ ] **Step 5: Apply the proven filter to the formal repository**

Only after Tasks 9, 10.2, and 10.4 are green, re-fetch the private notes remote and recheck its three hashes, require the formal status to be clean, recheck the filter-helper and replace-rule SHA-256 values, and run the same helper against the formal repository with `-Force` (the helper adds only `--force`; all content rules remain identical). Rename the active branch to `main`, repeat the machine equivalence/scanning gates and the complete local release suite, and confirm the discovered test count/result matches the pre-filter candidate. If filtering fails, do not reset or repair in place; clone the verified bundle into a new absent recovery directory and stop.

---

### Task 11: Create, push, and verify the public GitHub repository

**Files/State:**
- Formal remote: `https://github.com/Meow-saucee/intelligent-ticket-system.git`.
- GitHub settings: public, default `main`, approved description/topics, Issues enabled, private vulnerability reporting enabled.

**Interfaces:**
- Produces: the live open-source repository and final remote/CI evidence.

- [ ] **Step 1: Create an empty public repository in the verified account**

Using the already-approved browser workflow, reconfirm the visible account is `Meow-saucee`, create `intelligent-ticket-system` as **Public**, and do not initialize README, License, or `.gitignore`. If the name exists privately, stop and report the conflict rather than choosing another name.

- [ ] **Step 2: Push only sanitized `main` using Git/GCM**

Add the single origin URL, verify it character-for-character, inspect `git status`, `git log`, and `git remote -v`, then run `git push -u origin main`. Never use `--mirror`, `--all`, or a first-push force. If push fails after repository creation, change the incomplete repository to private and stop.

- [ ] **Step 3: Configure and visually verify repository metadata**

In GitHub web, set description exactly to `Local-first Python CLI ticket system with SQLite persistence, human-reviewed AI triage, audit trails, and prompt-injection evaluation.` and topics exactly to `python`, `sqlite`, `cli`, `ticket-system`, `ai-triage`, `human-in-the-loop`, `prompt-injection`, and `llm-evaluation`. Keep Issues enabled, enable private vulnerability reporting, and confirm default branch `main`, MIT detection, README badges, Mermaid, CLI blocks, and every documentation/result link. Do not enable branch protection, Projects, Wiki, Discussions, Pages, Releases, or PyPI publishing in this phase.

- [ ] **Step 4: Wait for all GitHub Actions jobs**

Use the Actions web page to wait until all eight OS/Python matrix jobs finish; confirm the two Python 3.14 demo steps ran on their matching OS and no step used a real AI key. Any failure reopens the matching local task; fix with TDD, rerun local gates, commit, push normally, and wait again.

- [ ] **Step 5: Perform final authenticated and anonymous checks**

Confirm logged-in access to the private notes repository; in a fresh unauthenticated browser context require the public repository to load and the notes repository to return not found. In a new absent directory under ignored `tmp/open-source-release/remote-check/`, run a normal anonymous single-branch clone of public `main`; require its HEAD to equal `git ls-remote ... refs/heads/main`, require only the expected local `main` plus `origin/main`, and run install, full tests, compile, and offline demo gates there. Record public URL, remote `main` HEAD, workflow URL/conclusion, license detection, test matrix, and final sensitive-object scan. Update the private notes `progress.md`/`task_plan.md` with final completion and push a private-only closing commit; record that the final private history is then five filtered historical commits plus two private-only checkpoint/closing commits.

- [ ] **Step 6: Final completion gate**

Invoke `superpowers:verification-before-completion`. Re-run local status/remote/log checks and report any retained local-only bundle/HANDOFF paths without publishing their contents. Mark the project published only when local release gates, private visibility, public accessibility, and all CI jobs are evidenced.
