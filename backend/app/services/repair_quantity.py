"""修补面积折算工程量的共用口径。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any, Iterable

AREA_FIELD = "修补面积"
QUANTITY_FIELD = "工程量"

# 当前按面积 1:1 折算；若以后材料配比调整，只改这一处。
_QUANTITY_RATIO = Decimal("1")
_QUANTITY_SCALE = Decimal("0.01")


def repair_quantity(area: Any, stored_quantity: Any = None) -> float:
    """把修补面积折算为工程量，并统一保留两位小数。

    早期示例数据中的面积可能不是数字；这类历史记录沿用原“用料数量”，
    避免列表和详情的既有表现发生变化。
    """
    area_text = str(area or "").strip()
    try:
        area_value = Decimal(area_text)
        if not area_value.is_finite():
            raise InvalidOperation
    except InvalidOperation:
        try:
            return float(stored_quantity)
        except (TypeError, ValueError):
            return 0.0

    with localcontext() as context:
        context.prec = max(50, len(area_text) + 10)
        quantity = (area_value * _QUANTITY_RATIO).quantize(
            _QUANTITY_SCALE, rounding=ROUND_HALF_UP
        )
    return float(quantity)


def with_repair_quantity(row: dict[str, Any]) -> dict[str, Any]:
    """返回带同一份工程量的修补单副本，不改动仓库中的原始记录。"""
    result = dict(row)
    result[QUANTITY_FIELD] = repair_quantity(
        result.get(AREA_FIELD), result.get("用料数量")
    )
    return result


def total_repair_quantity(rows: Iterable[dict[str, Any]]) -> float:
    """统计汇总使用逐项折算后的工程量，避免先求和再取整造成差异。

    面积不是数字的历史记录在列表、详情中保留原“用料数量”的展现，但不会
    被折算进工程量汇总，避免改写历史统计口径。
    """
    total = Decimal("0")
    for row in rows:
        area_text = str(row.get(AREA_FIELD) or "").strip()
        try:
            area_value = Decimal(area_text)
            if not area_value.is_finite():
                raise InvalidOperation
        except InvalidOperation:
            continue
        total += Decimal(str(repair_quantity(area_value)))
    return float(total.quantize(_QUANTITY_SCALE, rounding=ROUND_HALF_UP))
