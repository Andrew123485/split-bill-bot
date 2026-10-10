import os
import json
from pathlib import Path
from starlette.applications import Starlette
from starlette.responses import JSONResponse, FileResponse, HTMLResponse
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

import database
import splitter
from config import BASE_DIR, BOT_TOKEN

FRONTEND_DIR = BASE_DIR / "frontend"


async def get_bill_api(request):
    bill_id = request.path_params.get("bill_id", "latest")
    bill = database.get_bill(bill_id)

    if not bill:
        latest = database.get_latest_bill()
        if latest:
            bill = latest
            bill_id = bill["id"]
        else:
            return JSONResponse({"bill": None, "split": None, "empty": True})

    # If bill has total amount from QR/fiscal but 0 items entered yet, create a default shared pool item
    if len(bill.get("items", [])) == 0 and bill.get("total_amount", 0.0) > 0:
        database.add_item_to_bill(bill_id, "Общая покупка (супермаркет)", float(bill["total_amount"]), 1.0, "shared")
        bill = database.get_bill(bill_id)

    # Compute current split
    split_data = splitter.calculate_split(bill_id)
    return JSONResponse({
        "bill": bill,
        "split": split_data,
    })


async def get_latest_bill_api(request):
    user_id = request.query_params.get("user_id")
    u_id = int(user_id) if user_id and user_id.isdigit() else None
    bill = database.get_latest_bill(u_id)
    if not bill:
        return JSONResponse({"bill": None, "split": None, "empty": True})

    split_data = splitter.calculate_split(bill["id"])
    return JSONResponse({"bill": bill, "split": split_data})


async def list_bills_api(request):
    user_id = request.query_params.get("user_id")
    u_id = int(user_id) if user_id and user_id.isdigit() else None
    bills = database.get_all_bills(u_id)
    return JSONResponse({"bills": bills})


async def clear_bills_api(request):
    database.clear_all_bills()
    return JSONResponse({"ok": True, "message": "Все чеки успешно удалены"})


async def delete_bill_api(request):
    bill_id = request.path_params["bill_id"]
    database.delete_bill(bill_id)
    latest = database.get_latest_bill()
    return JSONResponse({"ok": True, "latest_bill_id": latest["id"] if latest else None})


async def create_demo_bill_api(request):
    demo_id = database.get_or_create_demo_bill()
    bill = database.get_bill(demo_id)
    split_data = splitter.calculate_split(demo_id)
    return JSONResponse({"ok": True, "bill": bill, "split": split_data})


async def add_participant_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    name = body.get("name", "").strip()
    is_nondrinker = bool(body.get("is_nondrinker", False))

    if not name:
        return JSONResponse({"error": "Имя участника обязательно"}, status_code=400)

    virtual_id = database.add_participant_manual(bill_id, name, is_nondrinker)
    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)
    return JSONResponse({"ok": True, "user_id": virtual_id, "bill": bill, "split": split_data})


async def update_participant_name_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    user_id = body.get("user_id")
    name = body.get("name", "").strip()

    if not user_id or not name:
        return JSONResponse({"error": "user_id и имя обязательны"}, status_code=400)

    database.update_participant_name(bill_id, int(user_id), name)
    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)
    return JSONResponse({"ok": True, "bill": bill, "split": split_data})


async def set_payer_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    payer_user_id = body.get("payer_user_id")
    payer_name = body.get("payer_name", "")
    payer_phone = body.get("payer_phone")
    payer_bank = body.get("payer_bank")

    if not payer_user_id or not payer_name:
        return JSONResponse({"error": "Укажите участника-плательщика"}, status_code=400)

    database.set_bill_payer(
        bill_id=bill_id,
        payer_user_id=int(payer_user_id),
        payer_name=payer_name,
        payer_phone=payer_phone,
        payer_bank=payer_bank,
    )

    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)
    return JSONResponse({"ok": True, "bill": bill, "split": split_data})



async def join_bill_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    user_id = body.get("user_id")
    name = body.get("name", "Гость")
    username = body.get("username")
    is_nondrinker = body.get("is_nondrinker")

    if not user_id:
        return JSONResponse({"error": "user_id обязателен"}, status_code=400)

    database.add_or_update_participant(
        bill_id=bill_id,
        user_id=int(user_id),
        name=name,
        username=username,
        is_nondrinker=is_nondrinker,
    )

    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)
    return JSONResponse({"ok": True, "bill": bill, "split": split_data})


async def toggle_claim_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    item_id = body.get("item_id")
    user_id = body.get("user_id")

    if not item_id or not user_id:
        return JSONResponse({"error": "item_id и user_id обязательны"}, status_code=400)

    is_claimed = database.toggle_item_claim(bill_id, int(item_id), int(user_id))
    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)

    return JSONResponse({
        "ok": True,
        "is_claimed": is_claimed,
        "bill": bill,
        "split": split_data,
    })


async def toggle_nondrinker_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    user_id = body.get("user_id")
    if not user_id:
        return JSONResponse({"error": "user_id обязателен"}, status_code=400)

    new_status = database.toggle_nondrinker(bill_id, int(user_id))
    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)

    return JSONResponse({
        "ok": True,
        "is_nondrinker": new_status,
        "bill": bill,
        "split": split_data,
    })


async def add_item_api(request):
    bill_id = request.path_params["bill_id"]
    try:
        body = await request.json()
    except Exception:
        body = {}

    name = body.get("name", "").strip()
    price = float(body.get("price", 0.0))
    quantity = float(body.get("quantity", 1.0))
    category = body.get("category", "shared")

    if not name or price <= 0:
        return JSONResponse({"error": "Укажите название и корректную цену"}, status_code=400)

    database.add_item_to_bill(bill_id, name, price, quantity, category)
    split_data = splitter.calculate_split(bill_id)
    bill = database.get_bill(bill_id)

    return JSONResponse({"ok": True, "bill": bill, "split": split_data})


async def report_api(request):
    bill_id = request.path_params["bill_id"]
    split_data = splitter.calculate_split(bill_id)
    report_text = splitter.format_telegram_report(split_data)
    return JSONResponse({"split": split_data, "report_text": report_text})


async def notify_chat_api(request):
    """Sends the formatted final settlement directly to the Telegram chat of the bill."""
    bill_id = request.path_params["bill_id"]
    bill = database.get_bill(bill_id)
    if not bill:
        return JSONResponse({"error": "Чек не найден"}, status_code=404)

    chat_id = bill.get("chat_id") or bill.get("payer_user_id")
    split_data = splitter.calculate_split(bill_id)
    report_text = splitter.format_telegram_report(split_data)

    # Use requests/httpx to send message via Telegram Bot API
    import urllib.request
    import urllib.parse

    tg_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": report_text,
        "parse_mode": "Markdown",
    }

    try:
        req = urllib.request.Request(
            tg_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode())
            return JSONResponse({"ok": True, "tg_response": resp_data})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def serve_index(request):
    return FileResponse(
        FRONTEND_DIR / "index.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
    )


middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
]

routes = [
    Route("/api/bills", list_bills_api, methods=["GET"]),
    Route("/api/bills/clear", clear_bills_api, methods=["POST"]),
    Route("/api/bill/demo/create", create_demo_bill_api, methods=["POST"]),
    Route("/api/bill/latest", get_latest_bill_api, methods=["GET"]),
    Route("/api/bill/{bill_id}", get_bill_api, methods=["GET"]),
    Route("/api/bill/{bill_id}/delete", delete_bill_api, methods=["POST", "DELETE"]),
    Route("/api/bill/{bill_id}/join", join_bill_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/claim", toggle_claim_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/toggle_nondrinker", toggle_nondrinker_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/add_item", add_item_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/add_participant", add_participant_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/update_name", update_participant_name_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/set_payer", set_payer_api, methods=["POST"]),
    Route("/api/bill/{bill_id}/report", report_api, methods=["GET"]),
    Route("/api/bill/{bill_id}/notify_chat", notify_chat_api, methods=["POST"]),
    Route("/", serve_index, methods=["GET"]),
    Route("/bill/{bill_id}", serve_index, methods=["GET"]),
    Mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static"),
]


app = Starlette(debug=True, routes=routes, middleware=middleware)
