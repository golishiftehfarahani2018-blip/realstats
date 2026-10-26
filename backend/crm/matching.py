"""Pure deterministic matching. Amounts remain integers; no AI, float or implicit conversion."""


def evaluate(demand, offering):
    reasons = []

    def criterion(code, label, matched, required, weight):
        reasons.append(
            {
                "criterion": code,
                "label": label,
                "matched": bool(matched),
                "required": required,
                "weight": weight,
            }
        )

    p = offering.property
    criterion("kind", "نوع ملک", demand.kind == p.kind, True, 20)
    criterion(
        "transaction",
        "نوع معامله",
        demand.transaction == offering.transaction,
        True,
        20,
    )
    criterion(
        "area", "بازه متراژ", demand.area_min <= p.area <= demand.area_max, True, 20
    )
    if demand.transaction == "sale":
        budget = (
            demand.budget_min_toman <= offering.price_toman <= demand.budget_max_toman
        )
    else:
        budget = (
            offering.deposit_toman <= demand.deposit_max_toman
            and offering.rent_toman <= demand.rent_max_toman
        )
    if demand.transaction=="sale" and getattr(offering,"negotiable_price",False):budget=False
    criterion("budget", "قیمت توافقی؛ نیازمند استعلام" if getattr(offering,"negotiable_price",False) else "بودجه مستقل فروش یا ودیعه و اجاره", budget, True, 20)
    criterion(
        "district",
        "محله ترجیحی",
        not demand.districts or p.district in demand.districts,
        False,
        20,
    )
    eligible = all(r["matched"] for r in reasons if r["required"])
    return {
        "eligible": eligible,
        "score": sum(r["weight"] for r in reasons if r["matched"]) if eligible else 0,
        "reasons": reasons,
        "rules_version": "1",
    }
