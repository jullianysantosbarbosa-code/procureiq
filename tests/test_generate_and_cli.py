import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from procureiq import analytics, cli, db, generate


class GenerateTests(unittest.TestCase):
    def test_same_seed_gives_same_data(self):
        self.assertEqual(generate.generate_rows(n=50, seed=7), generate.generate_rows(n=50, seed=7))

    def test_different_seed_gives_different_data(self):
        self.assertNotEqual(generate.generate_rows(n=50, seed=1), generate.generate_rows(n=50, seed=2))

    def test_injected_red_flags_are_detectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data.csv"
            generate.write_csv(generate.generate_rows(), path)
            conn = db.connect()
            db.load_csv(conn, path)
            self.assertGreaterEqual(len(analytics.find_split_purchases(conn)), 3)
            self.assertGreaterEqual(len(analytics.find_outliers(conn)), 3)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = str(Path(self.tmp.name) / "data.csv")
        generate.write_csv(generate.generate_rows(n=120, seed=3), self.csv)

    def run_cli(self, *args):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = cli.main(list(args))
        return code, buffer.getvalue()

    def test_suppliers_table(self):
        code, out = self.run_cli("suppliers", self.csv, "--top", "3")
        self.assertEqual(code, 0)
        self.assertIn("Supplier", out)
        self.assertEqual(len(out.strip().splitlines()), 5)  # header, rule, 3 rows

    def test_json_output_is_valid(self):
        code, out = self.run_cli("monthly", self.csv, "--json")
        self.assertEqual(code, 0)
        self.assertIn("month", json.loads(out)[0])

    def test_summary_runs(self):
        code, out = self.run_cli("summary", self.csv)
        self.assertEqual(code, 0)
        self.assertIn("Total spend", out)

    def test_missing_file_returns_error_code(self):
        buffer = io.StringIO()
        with contextlib.redirect_stderr(buffer):
            code = cli.main(["summary", "does-not-exist.csv"])
        self.assertEqual(code, 2)
        self.assertIn("error:", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
