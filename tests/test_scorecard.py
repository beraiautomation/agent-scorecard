"""Tests for the checkers, including attempts to game them. Run: python -m unittest -v"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from scorecard import checks  # noqa: E402
from scorecard.leaderboard import table  # noqa: E402
from scorecard.report import render  # noqa: E402
from scorecard.runner import build_argv, build_result, score  # noqa: E402
from scorecard.tasks import apply_solution, copy_workspace, load_tasks  # noqa: E402

TASKS = {t.id: t for t in load_tasks()}


class TaskCase(unittest.TestCase):
    task_id = ""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.dir = copy_workspace(TASKS[self.task_id], self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, name, text):
        (self.dir / name).write_text(text, encoding="utf-8")

    def result(self):
        return score(TASKS[self.task_id], self.tmp)

    def failed_checks(self):
        return [c["name"] for c in self.result()["checks"] if not c["ok"]]


class FixBug(TaskCase):
    task_id = "1-fix-bug"

    def test_solution_passes(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.assertTrue(self.result()["passed"])

    def test_hardcoding_the_visible_tests_fails(self):
        self.write("cart.py", (
            "def cart_total(items, discount_code=None):\n"
            "    key = (str(items), discount_code)\n"
            "    return {\n"
            "        (str([{'price': 10.0, 'qty': 2}, {'price': 5.0, 'qty': 1}]), None): 30.0,\n"
            "        (str([{'price': 25.0, 'qty': 2}]), None): 50.0,\n"
            "        (str([{'price': 50.0, 'qty': 2}]), 'SAVE10'): 90.0,\n"
            "        (str([{'price': 20.0, 'qty': 1}]), 'FREE'): 25.0,\n"
            "    }.get(key, 0)\n"))
        failed = self.failed_checks()
        self.assertNotIn("visible tests pass", failed)
        self.assertIn("hidden tests pass", failed)

    def test_editing_the_test_file_fails(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.write("test_cart.py", "print('4 of 4 tests passed')\n")
        self.assertIn("test_cart.py not changed", self.failed_checks())

    def test_discount_before_shipping_bug_is_caught(self):
        self.write("cart.py", (
            "def cart_total(items, discount_code=None):\n"
            "    s = sum(i['price'] * i['qty'] for i in items)\n"
            "    if discount_code == 'SAVE10':\n"
            "        s *= 0.9\n"
            "    return round(s + (0 if s >= 50 else 5), 2)\n"))
        self.assertIn("hidden tests pass", self.failed_checks())


PAGE = """<!doctype html><html><head><meta name="viewport" content="width=device-width"></head><body>
<h1>Bean There</h1><p>Hi!</p><h2>Menu</h2><p>Latte $3.50 Mocha $4.00 Tea $2.00 Flat white $3.75</p>
<h2>Hours</h2><p>{hours}</p><h2>Contact</h2><p>5 Oak Avenue, Leeds. Call 0113 496 0000</p></body></html>"""


class BuildPage(TaskCase):
    task_id = "2-build-page"

    def test_solution_passes(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.assertTrue(self.result()["passed"])

    def test_day_ranges_count(self):
        self.write("index.html", PAGE.format(hours="Mon - Fri 7-6, Sat to Sun 8-4"))
        self.assertTrue(self.result()["passed"], self.failed_checks())

    def test_missing_sunday_fails(self):
        self.write("index.html", PAGE.format(hours="Monday to Saturday 7-6"))
        self.assertIn("hours for all 7 days", self.failed_checks())

    def test_no_mobile_support_fails(self):
        html = PAGE.format(hours="Mon - Sun 8-6").replace('<meta name="viewport" content="width=device-width">', "")
        self.write("index.html", html)
        self.assertIn("works on phones", self.failed_checks())

    def test_wrong_order_fails(self):
        html = PAGE.format(hours="Mon - Sun 8-6").replace("<h1>Bean There</h1>", "").replace("</body>", "<p>Bean There</p></body>")
        self.write("index.html", html)
        self.assertIn("sections in the right order", self.failed_checks())


class PdfSummary(TaskCase):
    task_id = "3-pdf-summary"

    def test_solution_passes(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.assertTrue(self.result()["passed"])

    def test_made_up_number_fails(self):
        self.write("summary.txt", "\n".join([
            "- Revenue was 4.5 million pounds.", "- 3,100 bikes sold.", "- York shop opened.",
            "- 820 Care members.", "- 46 staff."]))
        failed = self.failed_checks()
        self.assertIn("no made-up numbers", failed)

    def test_six_bullets_fails(self):
        apply_solution(TASKS[self.task_id], self.dir)
        with (self.dir / "summary.txt").open("a", encoding="utf-8") as fh:
            fh.write("- Satisfaction was 4.6 out of 5.\n")
        self.assertIn("exactly 5 bullet points", self.failed_checks())

    def test_short_forms_and_numbered_lists_are_fine(self):
        self.write("summary.txt", "\n".join([
            "1. Revenue hit £4.2m, up 20% on 3.5m.", "2. York shop cost £180k.",
            "3. 1,240 of 3,100 bikes were electric.", "4. Staff grew from 38 to 46.",
            "5. Satisfaction 4.6/5 from 2,900 reviews."]))
        self.assertTrue(self.result()["passed"], self.failed_checks())

    def test_too_vague_fails(self):
        self.write("summary.txt", "- Good year.\n- Busy year.\n- Some problems.\n- Happy customers.\n- More plans.\n")
        self.assertIn("covers 4+ key facts", self.failed_checks())


class CsvTotals(TaskCase):
    task_id = "4-csv-totals"

    def test_solution_passes(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.assertTrue(self.result()["passed"])

    def test_other_formats_are_fine(self):
        self.write("results.txt", "Ana | $55.50\nBen | $33.00\nChen | $40.00\nDina | $28.00\nTOTAL | $156.50\n")
        self.assertTrue(self.result()["passed"], self.failed_checks())

    def test_counting_refunds_fails(self):
        self.write("results.txt", "Ana: 63.75\nBen: 33.00\nChen: 62.10\nDina: 28.00\nTotal: 186.85\n")
        failed = self.failed_checks()
        self.assertIn("every customer total is right", failed)
        self.assertIn("total line is right", failed)


class Refactor(TaskCase):
    task_id = "5-refactor"

    def test_solution_passes(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.assertTrue(self.result()["passed"])

    def test_untouched_code_fails_on_length(self):
        self.assertEqual(self.failed_checks(), ["code is at least 20% shorter"])

    def test_changed_output_fails(self):
        apply_solution(TASKS[self.task_id], self.dir)
        code = (self.dir / "report.py").read_text().replace('"Note: large team"', '"Note: big team"')
        self.write("report.py", code)
        self.assertIn("same output on 302 hidden inputs", self.failed_checks())

    def test_editing_the_test_file_fails(self):
        apply_solution(TASKS[self.task_id], self.dir)
        self.write("test_report.py", "print('3 of 3 tests passed')\n")
        self.assertIn("test_report.py not changed", self.failed_checks())


class Plumbing(unittest.TestCase):
    def test_build_argv_puts_prompt_in_one_argument(self):
        argv = build_argv("python -c pass {prompt}", "fix the bug, please")
        self.assertEqual(argv[-1], "fix the bug, please")

    def test_build_argv_appends_prompt_when_missing(self):
        self.assertEqual(build_argv("python -c pass", "hi")[-1], "hi")

    def test_report_and_table_render(self):
        tasks = [dict(number=1, id="1-fix-bug", title="Fix a bug", passed=True, seconds=90,
                      helped=False, peak_ram_gb=7.1, ram_added_gb=0.4,
                      checks=[{"name": "x", "ok": True, "detail": "<b>"}])]
        result = build_result("Test <Agent>", "m", "manual", None, [{"run": 1, "folder": "f", "tasks": tasks}])
        html = render(result)
        self.assertIn("Test &lt;Agent&gt;", html)
        self.assertIn("1/1", html)
        self.assertIn("| Test <Agent> |", table([result]))

    def test_auto_mode_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            cmd = f'"{sys.executable}" "{REPO / "tests" / "fake_agent.py"}" {{prompt}}'
            proc = subprocess.run(
                [sys.executable, "-m", "scorecard", "run", "--agent", "Fake Agent", "--cmd", cmd,
                 "--runs-dir", tmp, "--no-open", "--repeat", "2"],
                cwd=REPO, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            runs = sorted(Path(tmp).iterdir())
            self.assertEqual(len(runs), 2)
            data = json.loads((runs[0] / "scorecard.json").read_text(encoding="utf-8"))
            self.assertEqual(data["summary"]["passed"], 5)
            self.assertEqual(data["summary"]["passed_every_run"], 5)
            self.assertTrue((runs[0] / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
