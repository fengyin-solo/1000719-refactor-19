"""坑槽修补业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.services.repair_quantity import total_repair_quantity, with_repair_quantity
from app.store import store

MODULE = "pothole"
REQUIRED_FIELDS = ["修补单号", "所在路段", "修补面积"]
STATUS_ORDER = ["待安排", "修补中", "已完成", "已取消"]
ACTION_RULES = {"安排修补": "修补中", "确认完成": "已完成", "取消修补": "已取消"}
NEGATIVE_ACTIONS = []


class PotholeService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("修补单号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        page_rows = [with_repair_quantity(row) for row in rows[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return with_repair_quantity(entry) if entry is not None else None

    def summary(self) -> dict[str, Any]:
        rows = store.rows(MODULE)
        current_month = date.today().strftime("%Y-%m")
        month_rows = [
            row for row in rows
            if str(row.get("完成日期") or "").startswith(current_month)
        ]
        return {
            "待安排修补": sum(1 for row in rows if row.get("status") == STATUS_ORDER[0]),
            "本月修补面积": total_repair_quantity(month_rows),
            "取消单数": sum(1 for row in rows if row.get("status") == STATUS_ORDER[-1]),
        }

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return with_repair_quantity(entry), []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"修补单 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于坑槽修补可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return with_repair_quantity(entry), f"修补单已{action}"
