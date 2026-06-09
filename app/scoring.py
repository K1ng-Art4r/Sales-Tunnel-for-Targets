from decimal import ROUND_HALF_UP, Decimal


def calculate_express_operation_savings(accountants_count: int, monthly_salary_rub: int) -> dict[str, int]:
    released_6 = int((Decimal(accountants_count) * Decimal("0.35")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    released_12 = int((Decimal(accountants_count) * Decimal("0.65")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    payroll_saved_6 = int(released_6 * monthly_salary_rub)
    payroll_saved_12 = int(released_12 * monthly_salary_rub)

    ai_cost_6 = int((Decimal(payroll_saved_6) * Decimal("0.2")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    ai_cost_12 = int((Decimal(payroll_saved_12) * Decimal("0.2")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    net_6 = int(payroll_saved_6 - ai_cost_6)
    net_12 = int(payroll_saved_12 - ai_cost_12)

    return {
        "released_6": released_6,
        "released_12": released_12,
        "payroll_saved_6": payroll_saved_6,
        "payroll_saved_12": payroll_saved_12,
        "ai_cost_6": ai_cost_6,
        "ai_cost_12": ai_cost_12,
        "net_6": net_6,
        "net_12": net_12,
    }


def calculate_precise_savings_from_express(
    express_result: dict[str, float],
    standardization_band: str,
    automation_band: str,
    advisory_band: str,
) -> dict[str, float]:
    advisory_multiplier = {
        "lt10": 1.00,
        "10_20": 0.95,
        "gt20": 0.85,
    }.get(advisory_band, 1.00)
    automation_multiplier = {
        "none": 1.00,
        "partial": 0.85,
        "systems": 0.65,
    }.get(automation_band, 1.00)
    standardization_multiplier = {
        "high": 1.00,
        "medium": 1.10,
        "low": 1.35,
    }.get(standardization_band, 1.00)

    weighted_k = (
        advisory_multiplier * 0.30
        + standardization_multiplier * 0.35
        + automation_multiplier * 0.35
    )

    express_min = min(express_result["net_6"], express_result["net_12"])
    express_max = max(express_result["net_6"], express_result["net_12"])
    precise_min = express_min * weighted_k
    precise_max = express_max * weighted_k

    return {
        "k": weighted_k,
        "k_advisory": advisory_multiplier,
        "k_standardization": standardization_multiplier,
        "k_automation": automation_multiplier,
        "precise_min_rub": precise_min,
        "precise_max_rub": precise_max,
    }
