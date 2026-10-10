import os
import sys
import unittest
from starlette.testclient import TestClient

sys.path.insert(0, os.path.dirname(__file__))

import database
from api import app

class TestSplitBillAPI(unittest.TestCase):

    def setUp(self):
        database.init_db()
        self.client = TestClient(app)

    def test_bill_lifecycle_api(self):
        # 1. Create a bill
        bill_id = database.create_bill(
            title="Тестовый магазин",
            payer_user_id=101,
            payer_name="Организатор",
            items=[
                {"name": "Сок", "price": 100, "quantity": 1, "total_price": 100, "category": "shared", "is_alcohol": False},
                {"name": "Пиво", "price": 200, "quantity": 1, "total_price": 200, "category": "alcohol", "is_alcohol": True},
            ]
        )

        # 2. GET /api/bill/{bill_id}
        res = self.client.get(f"/api/bill/{bill_id}")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["bill"]["title"], "Тестовый магазин")
        self.assertEqual(len(data["bill"]["items"]), 2)

        # 3. Friend joins: POST /api/bill/{bill_id}/join
        join_res = self.client.post(f"/api/bill/{bill_id}/join", json={
            "user_id": 202,
            "name": "Друг",
            "username": "friend"
        })
        self.assertEqual(join_res.status_code, 200)

        # 4. Friend toggles nondrinker: POST /api/bill/{bill_id}/toggle_nondrinker
        nd_res = self.client.post(f"/api/bill/{bill_id}/toggle_nondrinker", json={"user_id": 202})
        self.assertEqual(nd_res.status_code, 200)
        self.assertTrue(nd_res.json()["is_nondrinker"])

        # 5. Check calculation:
        # Juice (100) / 2 = 50 each
        # Beer (200) -> Friend is nondrinker -> Payer pays full 200
        # Friend owes 50
        split_res = self.client.get(f"/api/bill/{bill_id}")
        participants = split_res.json()["split"]["participants"]
        friend_stat = [p for p in participants if p["user_id"] == 202][0]
        self.assertEqual(friend_stat["total_consumed"], 50.0)

        print("[API TEST PASS] All endpoints passed.")


if __name__ == "__main__":
    unittest.main()
