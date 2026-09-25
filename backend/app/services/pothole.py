"""坑槽修补业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from app.store import store

MODULE = "pothole"
REQUIRED_FIELDS = ["修补单号", "所在路段", "修补面积"]
STATUS_ORDER = ["待安排", "修补中", "已完成", "已取消"]
ACTION_RULES = {"安排修补": "修补中", "确认完成": "已完成", "取消修补": "已取消"}
NEGATIVE_ACTIONS = []

# 修补面积 -> 工程量 的唯一折算口径：列表、详情、统计汇总都从这里取数，
# 要调整进位或取整规则只动这一处，不要在页面或路由里各自再算。
QUANTITY_PLACES = Decimal("0.01")
QUANTITY_ROUNDING = ROUND_HALF_UP
AREA_PATTERN = re.compile(r"^\s*([-+]?\d+(?:\.\d+)?)\s*(?:㎡|m²|平方米)?\s*$")


def _parse_area(area: Any) -> Decimal | None:
    """从修补面积字段读出数值（平方米）；不是数值或面积为负时返回 None。"""
    if isinstance(area, bool):
        return None
    if isinstance(area, (int, float)):
        text = str(area)
    elif isinstance(area, str):
        text = area
    else:
        return None
    match = AREA_PATTERN.match(text)
    if match is None:
        return None
    try:
        value = Decimal(match.group(1))
    except InvalidOperation:
        return None
    return value if value >= 0 else None


def engineering_quantity(area: Any) -> Decimal | None:
    """把修补面积折算成工程量：四舍五入保留两位小数；面积读不出数值时返回 None。"""
    value = _parse_area(area)
    if value is None:
        return None
    return value.quantize(QUANTITY_PLACES, rounding=QUANTITY_ROUNDING)


def format_quantity(quantity: Decimal | None) -> str | None:
    """工程量的统一展示格式：两位小数字符串；None 原样透传，页面显示为 —。"""
    if quantity is None:
        return None
    rounded = quantity.quantize(QUANTITY_PLACES, rounding=QUANTITY_ROUNDING)
    return f"{rounded:.2f}"


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
        return [self._with_quantity(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None
        return self._with_quantity(entry)

    @staticmethod
    def _with_quantity(row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情共用的展示行：附加工整量，只读折算，不回写存储里的原始数据。"""
        return {**row, "工程量": format_quantity(engineering_quantity(row.get("修补面积")))}

    def summary(self, *, today: date | None = None) -> dict[str, Any]:
        """统计汇总：与列表、详情同源，累计工程量就是各修补单工程量逐一折算后再求和。"""
        rows = store.rows(MODULE)
        month = (today or date.today()).strftime("%Y-%m")
        month_area = Decimal("0")
        total_quantity = Decimal("0")
        for row in rows:
            area = _parse_area(row.get("修补面积"))
            if area is not None and str(row.get("完成日期") or "").startswith(month):
                month_area += area
            if row.get("status") == "已取消":
                continue
            quantity = engineering_quantity(row.get("修补面积"))
            if quantity is not None:
                total_quantity += quantity
        cards = [
            {"label": "待安排修补", "value": sum(1 for row in rows if row.get("status") == "待安排")},
            {"label": "本月修补面积", "value": format_quantity(month_area)},
            {"label": "取消单数", "value": sum(1 for row in rows if row.get("status") == "已取消")},
            {"label": "累计工程量", "value": format_quantity(total_quantity)},
        ]
        return {"cards": cards}

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
        return self._with_quantity(entry), []

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
        return self._with_quantity(entry), f"修补单已{action}"
