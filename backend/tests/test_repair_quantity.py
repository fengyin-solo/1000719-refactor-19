import unittest
from datetime import date
from unittest.mock import patch

from app.services.pothole import PotholeService
from app.services.repair_quantity import (
    repair_quantity,
    total_repair_quantity,
    with_repair_quantity,
)


class RepairQuantityTests(unittest.TestCase):
    def test_rounding_uses_shared_half_up_rule(self):
        self.assertEqual(repair_quantity("1.235"), 1.24)
        self.assertEqual(repair_quantity("2.004"), 2.00)

    def test_non_numeric_historical_area_keeps_display_quantity(self):
        row = {"修补面积": "坑槽修补样例", "用料数量": 10}
        projected = with_repair_quantity(row)

        self.assertEqual(projected["工程量"], 10.0)
        self.assertNotIn("工程量", row)

    def test_summary_total_matches_each_projected_quantity(self):
        rows = [{"修补面积": "1.005"}, {"修补面积": "1.005"}]

        self.assertEqual(total_repair_quantity(rows), 2.02)
        self.assertEqual(
            total_repair_quantity(rows),
            sum(with_repair_quantity(row)["工程量"] for row in rows),
        )


class PotholeServiceTests(unittest.TestCase):
    def test_list_detail_and_summary_share_quantity_result(self):
        service = PotholeService()
        current_month = date.today().strftime("%Y-%m")
        rows = [
            {"id": 1, "status": "待安排", "修补面积": "1.005", "完成日期": f"{current_month}-01"},
            {"id": 2, "status": "已取消", "修补面积": "1.005", "完成日期": f"{current_month}-02"},
        ]
        original_rows = [dict(row) for row in rows]

        with patch("app.services.pothole.store.rows", return_value=rows), \
             patch("app.services.pothole.store.find", return_value=rows[0]):
            listed, _ = service.list_entries()
            detail = service.get_entry(1)
            summary = service.summary()

        self.assertEqual(listed[0]["工程量"], detail["工程量"])
        self.assertEqual(summary["本月修补面积"], 2.02)
        self.assertEqual(rows, original_rows)


if __name__ == "__main__":
    unittest.main()
