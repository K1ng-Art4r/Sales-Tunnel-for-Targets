from decimal import ROUND_HALF_UP, Decimal


EXPRESS_AI_AGENT_COST_RATE = Decimal("0.20")
EXPRESS_EFFECT_3_MONTHS_RATE = Decimal("0.50")
EXPRESS_EFFECT_12_MONTHS_RATE = Decimal("0.80")


def _round_decimal(value: Decimal) -> int:
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def calculate_express_operation_savings(accountants_count: int, monthly_salary_rub: int) -> dict[str, int]:
    accountants = Decimal(accountants_count)
    salary = Decimal(monthly_salary_rub)
    ai_agent_cost = _round_decimal(salary * EXPRESS_AI_AGENT_COST_RATE)
    unit_saving = int(monthly_salary_rub - ai_agent_cost)

    effect_3 = _round_decimal(accountants * Decimal(unit_saving) * EXPRESS_EFFECT_3_MONTHS_RATE)
    effect_12 = _round_decimal(accountants * Decimal(unit_saving) * EXPRESS_EFFECT_12_MONTHS_RATE)

    # Legacy values are still calculated for the existing DB / Google Sheets structure
    # and for the detailed calculation flow. Do not repurpose these keys for the
    # new user-facing 3- and 12-month express output.
    released_6 = _round_decimal(accountants * Decimal("0.35"))
    released_12 = _round_decimal(accountants * Decimal("0.65"))
    payroll_saved_6 = int(released_6 * monthly_salary_rub)
    payroll_saved_12 = int(released_12 * monthly_salary_rub)
    ai_cost_6 = _round_decimal(Decimal(payroll_saved_6) * EXPRESS_AI_AGENT_COST_RATE)
    ai_cost_12 = _round_decimal(Decimal(payroll_saved_12) * EXPRESS_AI_AGENT_COST_RATE)
    net_6 = int(payroll_saved_6 - ai_cost_6)
    net_12 = int(payroll_saved_12 - ai_cost_12)

    return {
        "ai_agent_cost": ai_agent_cost,
        "unit_saving": unit_saving,
        "regular_load_3_percent": int(EXPRESS_EFFECT_3_MONTHS_RATE * 100),
        "regular_load_12_percent": int(EXPRESS_EFFECT_12_MONTHS_RATE * 100),
        "effect_3": effect_3,
        "effect_12": effect_12,
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
