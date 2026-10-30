import asyncio
import json
import unittest
from urllib.parse import urlsplit

from backend.app.core.security import create_access_token
from backend.app.db.dependencies import get_db
from backend.app.main import app
from backend.app.models import User
from backend.tests import test_simulation_execution as execution_fixture


async def asgi_request(method, url, token=None, payload=None):
    """Exercise the actual ASGI app without a network socket or extra client library."""
    parts = urlsplit(url)
    messages = []
    headers = [] if token is None else [(b"authorization", f"Bearer {token}".encode())]
    body_bytes = b"" if payload is None else json.dumps(payload).encode()
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": parts.path,
        "raw_path": parts.path.encode(), "query_string": parts.query.encode(),
        "root_path": "", "headers": headers,
        "server": ("test", 80), "client": ("test", 1234),
    }

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    status = next(m["status"] for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return status, json.loads(body)


class SimulationApiTests(unittest.TestCase):
    def setUp(self):
        self.fixture = execution_fixture.SimulationExecutionTests()
        self.fixture.setUp()
        self.fixture.db.add(User(id=2, email="other@example.com", hashed_password="unused"))
        self.fixture.db.commit()

        def test_db():
            with self.fixture.factory() as db:
                yield db

        app.dependency_overrides[get_db] = test_db
        self.token = create_access_token("1")
        self.other_token = create_access_token("2")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.fixture.tearDown()

    def request(self, method, path, token=None, payload=None):
        return asyncio.run(asgi_request(method, path, token, payload))

    def test_create_start_execute_and_read_results(self):
        strategy = {
            "strategy_type": "random", "buy_probability": 50,
            "sell_probability": 50, "hold_probability": 0, "price_deviation_pct": 1,
        }
        config = {
            "name": "API experiment", "duration_steps": 3, "seed": 42,
            "background_initial_quote_balance": 1000,
            "background_min_order_volume": 1, "background_max_order_volume": 1,
            "test_initial_quote_balance": 1000,
            "test_min_order_volume": 1, "test_max_order_volume": 1,
            "instrument_configs": [{
                "instrument_id": 1, "initial_price": 100,
                "background_initial_base_balance": 10, "test_initial_base_balance": 10,
            }],
            "background_profiles": [{**strategy, "agent_count": 2}],
            "test_strategy": strategy,
        }
        status, simulation = self.request("POST", "/api/simulations", self.token, config)
        self.assertEqual(status, 201)
        url = f"/api/simulations/{simulation['id']}"
        status, run = self.request("POST", url + "/start", self.token)
        self.assertEqual(status, 201)
        self.assertEqual(run["engine_version"], "2")
        self.assertEqual(self.request("POST", url + "/start", self.token)[0], 409)
        self.assertEqual(self.request("PUT", url, self.token, config)[0], 409)
        self.fixture.run_all()
        status, result = self.request("GET", url + "/results", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["current_step"], 3)
        self.assertEqual(result["run_id"], run["id"])

    def test_authentication_and_ownership_for_all_new_endpoints(self):
        for path in ("results", "balances", "orders", "trades", "order-book?instrument_id=1"):
            url = f"/api/simulations/1/{path}"
            self.assertEqual(self.request("GET", url)[0], 401)
            self.assertEqual(self.request("GET", url, self.other_token)[0], 404)

    def test_progress_and_results_after_full_execution(self):
        self.fixture.run_all()
        status, run = self.request("GET", "/api/simulations/1/run", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["current_step"], 3)
        status, results = self.request("GET", "/api/simulations/1/results", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(float(results["portfolio_value"]), 3000)
        self.assertGreater(results["trade_count"], 0)

    def test_history_pagination_and_instrument_validation(self):
        self.fixture.run_all()
        status, page = self.request("GET", "/api/simulations/1/trades?limit=1", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(page), 1)
        sequence = page[0]["sequence_number"]
        status, second = self.request("GET", f"/api/simulations/1/trades?after={sequence}", self.token)
        self.assertEqual(status, 200)
        self.assertTrue(all(t["sequence_number"] > sequence for t in second))
        self.assertEqual(self.request("GET", "/api/simulations/1/trades?instrument_id=999", self.token)[0], 404)
        self.assertEqual(self.request("GET", "/api/simulations/1/orders?limit=1001", self.token)[0], 422)

    def test_stop_endpoint_and_balances(self):
        status, stopped = self.request("POST", "/api/simulations/1/stop", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(stopped["status"], "stopped")
        status, participants = self.request("GET", "/api/simulations/1/balances", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(len(participants), 3)
        self.assertTrue(all(float(b["reserved"]) == 0 for p in participants for b in p["balances"]))

    def test_book_and_explicit_run_id(self):
        status, book = self.request("GET", "/api/simulations/1/order-book?instrument_id=1&run_id=1", self.token)
        self.assertEqual(status, 200)
        self.assertEqual(book["run_id"], 1)
        self.assertEqual(book["bids"], [])
        self.assertEqual(self.request("GET", "/api/simulations/1/results?run_id=999", self.token)[0], 404)


if __name__ == "__main__":
    unittest.main()
