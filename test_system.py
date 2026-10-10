import os
import sys
import unittest

# Ensure SplitBillBot directory is on python path
sys.path.insert(0, os.path.dirname(__file__))
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


import database
import splitter
import receipt_parser


class TestSplitBillSystem(unittest.TestCase):

    def setUp(self):
        database.init_db()

    def test_01_qr_detection(self):
        img_path = r"C:\Users\Андрей\.gemini\antigravity\brain\fd2da23e-8bb5-46c6-af1d-dd213fb8fe05\.user_uploaded\media_1790106571325.jpg"
        if os.path.exists(img_path):
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            qr_res = receipt_parser.decode_qr_from_image(img_bytes)
            self.assertIsNotNone(qr_res, "QR code must be detected on user receipt")
            self.assertIn("1383.91", qr_res)
            params = receipt_parser.parse_fiscal_qr_string(qr_res)
            self.assertEqual(params.get("s"), "1383.91")
            self.assertEqual(params.get("i"), "25033")
            print(f"[TEST 1 PASS] QR Code correctly decoded: {qr_res}")

    def test_02_categorization(self):
        cat1, is_alco1 = receipt_parser.detect_category("Пиво Corona Extra 0.355л")
        self.assertEqual(cat1, "alcohol")
        self.assertTrue(is_alco1)

        cat2, is_alco2 = receipt_parser.detect_category("Пиво Балтика 0 безалкогольное")
        self.assertEqual(cat2, "shared")
        self.assertFalse(is_alco2)

        cat3, is_alco3 = receipt_parser.detect_category("Сигареты Marlboro Red")
        self.assertEqual(cat3, "personal")
        self.assertFalse(is_alco3)

        cat4, is_alco4 = receipt_parser.detect_category("Шашлык свиной Мираторг")
        self.assertEqual(cat4, "shared")
        self.assertFalse(is_alco4)
        print("[TEST 2 PASS] Categorization rules passed.")

    def test_03_text_parsing(self):
        sample_text = """
        1. Пиво Corona 600
        2. Шашлык из свинины 1200
        3. Чипсы Lays 2 шт 270
        4. Сигареты Chapman 250
        """
        items = receipt_parser.parse_receipt_text_lines(sample_text)
        self.assertEqual(len(items), 4)
        total = sum(i["total_price"] for i in items)
        self.assertEqual(total, 2320.0)
        print(f"[TEST 3 PASS] Text receipt parsed: {len(items)} items, total: {total} ₽")

    def test_04_splitter_logic(self):
        # Create test bill
        items = [
            {"name": "Мясо шашлык (общак)", "price": 1200.0, "quantity": 1, "total_price": 1200.0, "category": "shared", "is_alcohol": False},
            {"name": "Вино красное (алко)", "price": 900.0, "quantity": 1, "total_price": 900.0, "category": "alcohol", "is_alcohol": True},
            {"name": "Сигареты (личное)", "price": 300.0, "quantity": 1, "total_price": 300.0, "category": "personal", "is_alcohol": False},
        ]
        # Total = 2400.0
        bill_id = database.create_bill(
            title="Тестовая поездка",
            payer_user_id=1,
            payer_name="Андрей (Плательщик)",
            total_amount=2400.0,
            items=items,
        )

        # Participants:
        # User 1: Andrey (payer, drinks)
        # User 2: Masha (does NOT drink alcohol)
        database.add_or_update_participant(bill_id, 2, "Маша", is_nondrinker=True)
        # User 3: Vasya (drinks alcohol, also specifically claims cigarettes)
        database.add_or_update_participant(bill_id, 3, "Вася", is_nondrinker=False)

        # Vasya claims cigarettes (item 3)
        bill_data = database.get_bill(bill_id)
        cig_item = [it for it in bill_data["items"] if "Сигареты" in it["name"]][0]
        database.toggle_item_claim(bill_id, cig_item["id"], 3)

        # Calculate split:
        # Meat (1200): shared by 3 -> 400 each
        # Wine (900): alcohol, Masha doesn't drink -> shared by Andrey and Vasya (2 people) -> 450 each
        # Cigarettes (300): claimed by Vasya only -> 300 for Vasya
        #
        # Expected totals:
        # Andrey: 400 (meat) + 450 (wine) = 850
        # Masha:  400 (meat) = 400
        # Vasya:  400 (meat) + 450 (wine) + 300 (cigs) = 1150
        # Sum: 850 + 400 + 1150 = 2400.0!

        split = splitter.calculate_split(bill_id)
        part_map = {p["user_id"]: p for p in split["participants"]}

        self.assertAlmostEqual(part_map[1]["total_consumed"], 850.0, places=1)
        self.assertAlmostEqual(part_map[2]["total_consumed"], 400.0, places=1)
        self.assertAlmostEqual(part_map[3]["total_consumed"], 1150.0, places=1)

        # Transfers check:
        # Masha owes Andrey 400
        # Vasya owes Andrey 1150
        transfers = split["transfers"]
        self.assertEqual(len(transfers), 2)
        print("[TEST 4 PASS] Split calculation and non-drinker exclusions exact to the kopeck!")

        report_md = splitter.format_telegram_report(split)
        self.assertIn("Маша", report_md)
        self.assertIn("Без алко", report_md)
        print(f"[TEST 4 REPORT]:\n{report_md}")


if __name__ == "__main__":
    unittest.main()
