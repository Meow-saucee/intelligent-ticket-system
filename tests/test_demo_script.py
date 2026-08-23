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
