import re
import cv2
import numpy as np
import requests
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import parse_qs, urlparse
import config



# Keywords for automatic alcohol detection
ALCOHOL_KEYWORDS = [
    "пиво", "вино", "водка", "сидр", "коньяк", "виски", "джин", "ром",
    "шампанск", "просекко", "ликер", "ликёр", "медовух", "вермут",
    "хмел", "stella", "heineken", "corona", "guinness", "martini",
    "aperol", "whiskey", "gin", "beer", "wine", "cider", "водк", "эль", "ipa", "apa"
]

NON_ALCOHOL_EXCEPTIONS = [
    "безалк", "б/а", "0.0", "non-alcoholic", "нулевка", "нулёвка"
]

# Keywords for tobacco / personal items
TOBACCO_KEYWORDS = [
    "сигарет", "стик", "вейп", "iqos", "glo", "marlboro", "winston",
    "kent", "parliament", "sobranie", "chapman", "ld", "camel", "электронн"
]


def detect_category(item_name: str) -> Tuple[str, bool]:
    """
    Detects if item is alcohol, tobacco/personal, or general shared item.
    Returns: (category, is_alcohol)
    """
    name_lower = item_name.lower()

    # Check non-alcohol exceptions first (e.g. "Пиво Балтика б/а")
    for exc in NON_ALCOHOL_EXCEPTIONS:
        if exc in name_lower:
            return "shared", False

    # Check alcohol
    for alco in ALCOHOL_KEYWORDS:
        if re.search(r'\b' + re.escape(alco) + r'|\b' + re.escape(alco), name_lower):
            return "alcohol", True

    # Check tobacco
    for tob in TOBACCO_KEYWORDS:
        if tob in name_lower:
            return "personal", False

    return "shared", False


def decode_qr_from_image(image_bytes: bytes) -> Optional[str]:
    """
    Decodes QR code from raw image bytes using WeChat QRCode detector.
    """
    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        detector = cv2.wechat_qrcode_WeChatQRCode()
        results, _ = detector.detectAndDecode(img)
        if results and len(results) > 0 and results[0]:
            return results[0]
    except Exception as e:
        print(f"QR decode error: {e}")

    # Fallback to standard QRCodeDetector
    try:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        detector = cv2.QRCodeDetector()
        val, pts, _ = detector.detectAndDecode(img)
        if val:
            return val
    except Exception:
        pass

    return None


def parse_fiscal_qr_string(qr_str: str) -> Dict[str, str]:
    """
    Parses Russian fiscal QR parameters:
    Example: t=20260821T2050&s=1383.91&fn=7380440903024313&i=25033&fp=3622281079&n=1
    """
    parsed = {}
    if "&" in qr_str or "=" in qr_str:
        # Strip query part if full URL
        if "?" in qr_str:
            qr_str = qr_str.split("?", 1)[1]
        params = parse_qs(qr_str)
        for k, v in params.items():
            parsed[k] = v[0] if v else ""
    return parsed


def fetch_receipt_from_proverkacheka(qr_raw: str) -> Optional[Dict[str, Any]]:
    """
    Fetches official fiscal receipt items from proverkacheka.com API.
    """
    token = config.PROVERKACHEKA_TOKEN
    if not token:
        return None

    try:
        url = "https://proverkacheka.com/api/v1/check/get"
        s = requests.Session()
        s.trust_env = False
        response = s.post(
            url,
            data={"qrraw": qr_raw, "token": token},
            timeout=12,
        )
        if response.status_code == 200:
            res_json = response.json()
            if res_json.get("code") == 1 and "data" in res_json:
                check_data = res_json["data"].get("json", {})
                items = []
                for item in check_data.get("items", []):
                    name = item.get("name", "Товар")
                    price = float(item.get("price", 0)) / 100.0  # kopecks to rubles
                    qty = float(item.get("quantity", 1))
                    total = float(item.get("sum", price * qty)) / 100.0
                    category, is_alco = detect_category(name)
                    items.append({
                        "name": name,
                        "price": price,
                        "quantity": qty,
                        "total_price": total,
                        "category": category,
                        "is_alcohol": is_alco,
                    })
                return {
                    "title": check_data.get("user", "Магазин"),
                    "total_amount": float(check_data.get("totalSum", 0)) / 100.0,
                    "items": items,
                }
    except Exception as e:
        print(f"Proverkacheka API error: {e}")

    return None



def parse_receipt_text_lines(text: str) -> List[Dict[str, Any]]:
    """
    Parses plain text lines entered by user or OCR.
    Formats supported:
    - 'Пиво Corona 6 шт 600'
    - 'Чипсы Lay's 2 269.98'
    - 'Мясо для шашлыка 1200'
    - '1. Наггетсы Мираторг - 419.97'
    """
    items = []
    lines = text.strip().split("\n")

    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("---") or line.lower().startswith("итог"):
            continue

        # Clean leading numbers like "1. ", "1) "
        line = re.sub(r'^\d+[\.\)]\s*', '', line)

        # Regex to find price at the end: e.g. " 1383.91", " 250р", " - 419.97"
        match = re.search(r'[-–—:\s]+(?P<price>\d+[\.,]?\d*)\s*(?:руб|р|rub|₽)?\s*$', line, re.IGNORECASE)
        if match:
            price_str = match.group('price').replace(',', '.')
            try:
                total_price = float(price_str)
            except ValueError:
                continue

            name_part = line[:match.start()].strip(' -–—:')

            # Check if quantity is mentioned in name: "чипсы 2 шт" or "пиво x 3"
            qty = 1.0
            qty_match = re.search(r'(?:[xх*]\s*|(\d+[\.,]?\d*)\s*(?:шт|уп|кг|л)\b)', name_part, re.IGNORECASE)
            if qty_match:
                try:
                    matched_num = qty_match.group(1) or qty_match.group(0).strip('xх* ')
                    qty = float(matched_num.replace(',', '.'))
                except Exception:
                    qty = 1.0

            unit_price = round(total_price / qty, 2) if qty > 0 else total_price
            category, is_alco = detect_category(name_part)

            items.append({
                "name": name_part,
                "price": unit_price,
                "quantity": qty,
                "total_price": total_price,
                "category": category,
                "is_alcohol": is_alco,
            })

    return items


def get_sample_verny_receipt() -> Dict[str, Any]:
    """
    Parsed items from the user's uploaded receipt from 'Верный' (1383.91 ₽).
    Total matches 1383.91 ₽ perfectly.
    """
    raw_items = [
        {"name": "Пакет майка Верный", "price": 9.99, "quantity": 1, "total_price": 9.99},
        {"name": "Добрый напиток сок", "price": 99.99, "quantity": 1, "total_price": 99.99},
        {"name": "Мираторг Наггетсы из курицы", "price": 139.99, "quantity": 3, "total_price": 419.97},
        {"name": "Lay's чипсы макси бекон", "price": 134.99, "quantity": 2, "total_price": 269.98},
        {"name": "От Мартина Семечки Полоса", "price": 109.99, "quantity": 1, "total_price": 109.99},
        {"name": "Lay's Чипсы Рифленая Паприка", "price": 184.99, "quantity": 1, "total_price": 184.99},
        {"name": "Сигареты Marlboro", "price": 289.00, "quantity": 1, "total_price": 289.00},
    ]

    items = []
    for it in raw_items:
        cat, is_alco = detect_category(it["name"])
        items.append({
            **it,
            "category": cat,
            "is_alcohol": is_alco,
        })

    return {
        "title": "Магазин «Верный»",
        "total_amount": 1383.91,
        "items": items,
        "fiscal_fn": "7380440903024313",
        "fiscal_fd": "25033",
        "fiscal_fp": "3622281079",
        "date": "2026-08-21 20:50",
    }
