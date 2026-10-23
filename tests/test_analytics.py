import unittest

from procureiq import analytics

from helpers import make_conn


class SpendTests(unittest.TestCase):
    def setUp(self):
        self.conn = make_conn(
            [
                ("2025-01-05", "Acme", "IT", "IT Services", 600.0, 10),
                ("2025-01-20", "Acme", "IT", "IT Services", 400.0, 14),
                ("2025-02-03", "Beta", "HR", "Training", 1000.0, 6),
                ("2025-02-18", "Gamma", "HR", "Training", 2000.0, 8),
            ]
        )

    def test_spend_by_supplier_is_sorted_with_shares(self):
        result = analytics.spend_by_supplier(self.conn)
        self.assertEqual([r["supplier"] for r in result], ["Gamma", "Acme", "Beta"])
        self.assertEqual(result[0]["share_pct"], 50.0)
        self.assertEqual(result[1]["count"], 2)

    def test_spend_by_supplier_respects_limit(self):
        self.assertEqual(len(analytics.spend_by_supplier(self.conn, limit=1)), 1)

    def test_monthly_spend_groups_by_month(self):
        result = analytics.monthly_spend(self.conn)
        self.assertEqual(
            result,
            [
                {"month": "2025-01", "total_eur": 1000.0, "count": 2},
                {"month": "2025-02", "total_eur": 3000.0, "count": 2},
            ],
        )

    def test_lead_times_median_and_order(self):
        result = analytics.lead_times_by_category(self.conn)
        self.assertEqual(result[0]["category"], "IT Services")
        self.assertEqual(result[0]["median_days"], 12)
        self.assertEqual(result[0]["max_days"], 14)
        self.assertEqual(result[1]["median_days"], 7)

    def test_empty_database(self):
        empty = make_conn([])
        self.assertEqual(analytics.spend_by_supplier(empty), [])
        self.assertEqual(analytics.monthly_spend(empty), [])


class SplitPurchaseTests(unittest.TestCase):
    def test_flags_cluster_that_crosses_threshold(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 20_000, 5),
                ("2025-03-05", "Acme", "IT", "IT Services", 22_000, 5),
                ("2025-03-10", "Acme", "IT", "IT Services", 19_500, 5),
            ]
        )
        flags = analytics.find_split_purchases(conn)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].count, 3)
        self.assertEqual(flags[0].total_eur, 61_500.0)
        self.assertEqual(flags[0].ids, [1, 2, 3])

    def test_ignores_purchases_outside_window(self):
        conn = make_conn(
            [
                ("2025-01-01", "Acme", "IT", "IT Services", 30_000, 5),
                ("2025-06-01", "Acme", "IT", "IT Services", 30_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn), [])

    def test_does_not_combine_different_suppliers_or_departments(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 30_000, 5),
                ("2025-03-02", "Beta", "IT", "IT Services", 30_000, 5),
                ("2025-03-03", "Acme", "HR", "IT Services", 30_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn), [])

    def test_does_not_combine_different_categories(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 30_000, 5),
                ("2025-03-02", "Acme", "IT", "Training", 30_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn), [])

    def test_purchases_above_threshold_are_not_splits(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 60_000, 5),
                ("2025-03-02", "Acme", "IT", "IT Services", 70_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn), [])

    def test_small_totals_below_threshold_are_fine(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 10_000, 5),
                ("2025-03-02", "Acme", "IT", "IT Services", 12_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn), [])

    def test_custom_threshold_and_window(self):
        conn = make_conn(
            [
                ("2025-03-01", "Acme", "IT", "IT Services", 6_000, 5),
                ("2025-03-20", "Acme", "IT", "IT Services", 6_000, 5),
            ]
        )
        self.assertEqual(analytics.find_split_purchases(conn, threshold=10_000, window_days=10), [])
        self.assertEqual(len(analytics.find_split_purchases(conn, threshold=10_000, window_days=30)), 1)


class OutlierTests(unittest.TestCase):
    def test_flags_extreme_value(self):
        records = [("2025-01-01", "Acme", "IT", "Office Supplies", 100 + i * 10, 3) for i in range(10)]
        records.append(("2025-02-01", "Acme", "IT", "Office Supplies", 9_000, 3))
        flags = analytics.find_outliers(make_conn(records))
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].amount_eur, 9_000)

    def test_normal_data_has_no_outliers(self):
        records = [("2025-01-01", "Acme", "IT", "Office Supplies", 100 + i * 10, 3) for i in range(10)]
        self.assertEqual(analytics.find_outliers(make_conn(records)), [])

    def test_small_categories_are_skipped(self):
        records = [("2025-01-01", "Acme", "IT", "Rare", amount, 3) for amount in (10, 11, 5_000)]
        self.assertEqual(analytics.find_outliers(make_conn(records)), [])


if __name__ == "__main__":
    unittest.main()
