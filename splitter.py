from typing import Dict, List, Any
import database


def calculate_split(bill_id: str) -> Dict[str, Any]:
    """
    Calculates the exact breakdown of who owes what for a bill.
    Supports:
    - Personal / partial claims (1 or more people)
    - Shared pool (Общак)
    - Alcohol exclusion for non-drinkers
    - Debt settlement (minimal transfers)
    """
    bill = database.get_bill(bill_id)
    if not bill:
        return {"error": "Чек не найден"}

    participants = {p["user_id"]: p for p in bill["participants"]}
    if not participants:
        # If no participants yet, add payer
        payer_id = bill["payer_user_id"]
        participants[payer_id] = {
            "user_id": payer_id,
            "name": bill["payer_name"],
            "username": bill["payer_username"],
            "is_nondrinker": 0,
        }

    all_user_ids = list(participants.keys())
    drinkers = [u for u, p in participants.items() if not p["is_nondrinker"]]
    if not drinkers:
        # Fallback if everyone marked nondrinker but alcohol was bought
        drinkers = all_user_ids

    user_shares: Dict[int, float] = {u: 0.0 for u in all_user_ids}
    user_item_breakdown: Dict[int, List[Dict[str, Any]]] = {u: [] for u in all_user_ids}

    for item in bill["items"]:
        item_total = float(item["total_price"])
        item_name = item["name"]
        is_alco = bool(item["is_alcohol"] or item["category"] == "alcohol")
        claims = item["claimed_by"]

        if claims:
            # Item was explicitly claimed by 1 or more people
            eligible = [u for u in claims if u in participants]
            if not eligible:
                eligible = all_user_ids
        else:
            # Item is shared (общак)
            if is_alco:
                eligible = drinkers
            else:
                eligible = all_user_ids

        if not eligible:
            eligible = [bill["payer_user_id"]]

        share_per_person = round(item_total / len(eligible), 2)
        # Adjust last person for rounding precision
        remainder = round(item_total - (share_per_person * len(eligible)), 2)

        for i, u_id in enumerate(eligible):
            added = share_per_person + (remainder if i == 0 else 0.0)
            user_shares[u_id] = round(user_shares[u_id] + added, 2)
            user_item_breakdown[u_id].append({
                "item_id": item["id"],
                "name": item_name,
                "share": added,
                "total_price": item_total,
                "split_count": len(eligible),
                "is_alcohol": is_alco,
            })

    # Prepare summary per user
    user_summaries = []
    payer_id = bill["payer_user_id"]

    for u_id in all_user_ids:
        p = participants[u_id]
        total_consumed = round(user_shares[u_id], 2)
        paid = round(float(bill["total_amount"]), 2) if u_id == payer_id else 0.0
        net = round(paid - total_consumed, 2)

        user_summaries.append({
            "user_id": u_id,
            "name": p["name"],
            "username": p.get("username"),
            "is_nondrinker": bool(p.get("is_nondrinker")),
            "is_payer": (u_id == payer_id),
            "total_consumed": total_consumed,
            "paid": paid,
            "net": net,
            "items": user_item_breakdown[u_id],
        })

    # Calculate optimal transfers
    # Debtors: net < 0 (owe money)
    # Creditors: net > 0 (owed money)
    debtors = []
    creditors = []
    for s in user_summaries:
        if s["net"] < -0.01:
            debtors.append({"user_id": s["user_id"], "name": s["name"], "amount": -s["net"]})
        elif s["net"] > 0.01:
            creditors.append({"user_id": s["user_id"], "name": s["name"], "amount": s["net"]})

    transfers = []
    d_idx, c_idx = 0, 0
    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor = debtors[d_idx]
        creditor = creditors[c_idx]

        amount = min(debtor["amount"], creditor["amount"])
        if amount > 0.01:
            transfers.append({
                "from_user_id": debtor["user_id"],
                "from_name": debtor["name"],
                "to_user_id": creditor["user_id"],
                "to_name": creditor["name"],
                "amount": round(amount, 2),
            })

        debtor["amount"] -= amount
        creditor["amount"] -= amount

        if debtor["amount"] <= 0.01:
            d_idx += 1
        if creditor["amount"] <= 0.01:
            c_idx += 1

    return {
        "bill_id": bill_id,
        "title": bill["title"],
        "total_amount": float(bill["total_amount"]),
        "payer_id": payer_id,
        "payer_name": bill["payer_name"],
        "payer_phone": bill.get("payer_phone"),
        "payer_bank": bill.get("payer_bank"),
        "participants": user_summaries,
        "transfers": transfers,
    }


def format_telegram_report(split_result: Dict[str, Any]) -> str:
    """Formats the split calculation into a beautiful Telegram message."""
    title = split_result.get("title", "Общий чек")
    total = split_result.get("total_amount", 0.0)
    payer = split_result.get("payer_name", "Плательщик")
    phone = split_result.get("payer_phone")
    bank = split_result.get("payer_bank")

    lines = [
        f"🧾 **Расчёт по чеку: {title}**",
        f"💰 **Общая сумма:** `{total:.2f} ₽`",
        f"💳 **Оплатил(а):** {payer}",
        "",
        "👥 **Доля каждого участника:**",
    ]

    for p in split_result["participants"]:
        status_icons = []
        if p["is_payer"]:
            status_icons.append("👑 Оплатил(а)")
        if p["is_nondrinker"]:
            status_icons.append("🥤 Без алко")
        status_text = f" ({', '.join(status_icons)})" if status_icons else ""

        lines.append(f"• **{p['name']}**{status_text}: `{p['total_consumed']:.2f} ₽`")

    lines.append("")
    lines.append("🔄 **Кто кому переводит:**")

    if not split_result["transfers"]:
        lines.append("Все расходы покрыты или участников нет.")
    else:
        for t in split_result["transfers"]:
            lines.append(f"➡️ **{t['from_name']}** ➔ **{t['to_name']}**: `{t['amount']:.2f} ₽`")

    if phone or bank:
        lines.append("")
        lines.append("📲 **Реквизиты для перевода (СБП):**")
        if phone:
            lines.append(f"• Номер: `{phone}`")
        if bank:
            lines.append(f"• Банк: {bank}")

    lines.append("\n_Рассчитано через @warok18bot_")
    return "\n".join(lines)
