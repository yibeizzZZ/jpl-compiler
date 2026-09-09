"""Compiler smoke tests and source-input regressions; no native runtime needed."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
ASSEMBLY_FLAGS = (("-s",), ("-s", "-O1"), ("-s", "-O3"))
FIXTURE_NAMES = ("col", "crs", "dns", "mat", "sft")


class CompilerTests(unittest.TestCase):
    def run_compiler(self, source, *flags):
        return subprocess.run(
            [sys.executable, "-B", str(ROOT / "compiler.py"), *flags, str(source)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )

    def assert_compilation_succeeds(self, result):
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Compilation succeeded", result.stdout)

    def test_all_examples_pass_frontend(self):
        sources = [ROOT / "test.jpl", *sorted((ROOT / "examples").glob("*.jpl"))]
        for source in sources:
            for flag in ("-l", "-p", "-t"):
                with self.subTest(source=source.name, flag=flag):
                    self.assert_compilation_succeeds(self.run_compiler(source, flag))

    def test_frontend_rejects_invalid_source(self):
        cases = (
            ("-l", 'print "unterminated\n'),
            ("-p", "let = 1\n"),
            ("-t", "show missing_variable\n"),
            ("-t", "show 1 + true\n"),
            ("-t", "show [1, true]\n"),
            ("-t", "fn f() : int {\nreturn true\n}\n"),
        )
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.jpl"
            for flag, text in cases:
                with self.subTest(flag=flag, source=text):
                    source.write_text(text, encoding="utf-8")
                    result = self.run_compiler(source, flag)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn("Compilation succeeded", result.stdout)

    def test_scalar_function_emits_assembly(self):
        for flags in ASSEMBLY_FLAGS:
            with self.subTest(flags=flags):
                result = self.run_compiler(ROOT / "examples" / "subtract.jpl", *flags)
                self.assert_compilation_succeeds(result)
                self.assertIn("section .text", result.stdout)
                self.assertIn("call _subtract", result.stdout)
                self.assertIn("call _show", result.stdout)

    def test_neighboring_fixtures_do_not_replace_assembly(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in FIXTURE_NAMES:
                for index, flags in enumerate(ASSEMBLY_FLAGS):
                    with self.subTest(name=name, flags=flags):
                        case_dir = Path(directory) / f"{name}-{index}"
                        case_dir.mkdir()
                        source = case_dir / f"{name}.jpl"
                        source.write_text("show 42\n", encoding="utf-8")
                        original = self.run_compiler(source, *flags)
                        self.assert_compilation_succeeds(original)
                        for suffix in (".expected", ".expected.opt"):
                            Path(str(source) + suffix).write_text(
                                "UNRELATED_FIXTURE_CONTENT\n", encoding="utf-8"
                            )
                        result = self.run_compiler(source, *flags)
                        self.assert_compilation_succeeds(result)
                        self.assertEqual(result.stdout, original.stdout)

    def test_neighboring_fixtures_do_not_hide_invalid_source(self):
        with tempfile.TemporaryDirectory() as directory:
            for name in FIXTURE_NAMES:
                source = Path(directory) / f"{name}.jpl"
                source.write_text("show missing_variable\n", encoding="utf-8")
                for suffix in (".expected", ".expected.opt"):
                    Path(str(source) + suffix).write_text(
                        "UNRELATED_FIXTURE_CONTENT\n", encoding="utf-8"
                    )
                for flags in ASSEMBLY_FLAGS:
                    with self.subTest(name=name, flags=flags):
                        result = self.run_compiler(source, *flags)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertNotIn("Compilation succeeded", result.stdout)
                        self.assertNotIn("UNRELATED_FIXTURE_CONTENT", result.stdout)


if __name__ == "__main__":
    unittest.main()
