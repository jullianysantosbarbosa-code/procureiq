import tempfile
import unittest
from pathlib import Path

from procureiq import db

HEADER = "id,date,department,supplier,category,amount_eur,processing_days\n"


def write(tmp: str, body: str) -> Path:
    path = Path(tmp) / "data.csv"
    path.write_text(HEADER + body, encoding="utf-8")
    return path


class LoadCsvTests(unittest.TestCase):
    def test_loads_valid_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "1,2025-01-10,IT,Acme,IT Services,1500.50,12\n2,2025-02-01,HR,Beta,Training,300,5\n")
            conn = db.connect()
            self.assertEqual(db.load_csv(conn, path), 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM procurements").fetchone()[0], 2)

    def test_reloading_replaces_existing_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "1,2025-01-10,IT,Acme,IT Services,100,2\n")
            conn = db.connect()
            db.load_csv(conn, path)
            db.load_csv(conn, path)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM procurements").fetchone()[0], 1)

    def test_rejects_negative_amount_with_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "1,2025-01-10,IT,Acme,IT Services,100,2\n2,2025-01-11,IT,Acme,IT Services,-5,2\n")
            with self.assertRaisesRegex(ValueError, "line 3"):
                db.load_csv(db.connect(), path)

    def test_rejects_bad_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "1,10/01/2025,IT,Acme,IT Services,100,2\n")
            with self.assertRaisesRegex(ValueError, "line 2"):
                db.load_csv(db.connect(), path)

    def test_rejects_missing_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("id,date\n1,2025-01-01\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "missing columns"):
                db.load_csv(db.connect(), path)

    def test_invalid_file_leaves_existing_data_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = write(tmp, "1,2025-01-10,IT,Acme,IT Services,100,2\n")
            conn = db.connect()
            db.load_csv(conn, good)
            bad = Path(tmp) / "bad.csv"
            bad.write_text(HEADER + "9,2025-01-10,IT,Acme,IT Services,abc,2\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                db.load_csv(conn, bad)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM procurements").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
