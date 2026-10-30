import unittest
from decimal import Decimal as D

from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.app.db.base import Base
from backend.app.models import (
    Asset, Instrument, ParticipantBalance, Simulation, SimulationParticipant,
    SimulationRun, SimulationRunInstrument, Trade, User,
)
from backend.app.services.trading import (
    TradingError, cancel_order, get_order_book, get_price_history, place_order,
)


class TradingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        self.db.add_all([
            User(id=1, email="trading@example.com", hashed_password="unused"),
            Asset(id=1, symbol="USD", name="Dollar"),
            Asset(id=2, symbol="BTC", name="Bitcoin"),
            Asset(id=3, symbol="ETH", name="Ethereum"),
        ])
        self.db.flush()
        self.db.add_all([
            Instrument(id=1, base_asset_id=2, quote_asset_id=1),
            Instrument(id=2, base_asset_id=3, quote_asset_id=1),
            Simulation(
                id=1, owner_id=1, name="Trading", duration_steps=10, seed=42,
                background_initial_quote_balance=D(1000),
                background_min_order_volume=D(1), background_max_order_volume=D(10),
                test_initial_quote_balance=D(1000),
                test_min_order_volume=D(1), test_max_order_volume=D(10),
            ),
        ])
        self.db.flush()
        self.run = SimulationRun(
            id=1, simulation_id=1, seed=42, total_steps=10,
            engine_version="1", configuration_snapshot={},
        )
        self.db.add(self.run)
        self.db.flush()
        self.db.add_all([
            SimulationRunInstrument(run_id=1, instrument_id=i, initial_price=D(100), last_price=D(100))
            for i in (1, 2)
        ])
        for number in (1, 2, 3):
            participant = SimulationParticipant(
                id=number, run_id=1, sequence_number=number,
                participant_type="background", strategy_type="random",
                strategy_parameters={}, rng_seed=number,
                min_order_volume=D("0.00000001"), max_order_volume=D(10),
            )
            participant.balances = [
                ParticipantBalance(asset_id=asset, available=D(amount), reserved=D(0))
                for asset, amount in ((1, 1000), (2, 10), (3, 10))
            ]
            self.db.add(participant)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def order(self, participant, side, price, volume, instrument=1):
        return place_order(self.db, 1, participant, instrument, side, D(price), D(volume), 1)

    def balance(self, participant, asset):
        return self.db.scalar(select(ParticipantBalance).where(
            ParticipantBalance.participant_id == participant,
            ParticipantBalance.asset_id == asset,
        ))

    def trades(self):
        return list(self.db.scalars(select(Trade).order_by(Trade.sequence_number)))

    def assert_conserved(self):
        for asset, expected in ((1, D(3000)), (2, D(30)), (3, D(30))):
            balances = [self.balance(p, asset) for p in (1, 2, 3)]
            self.assertEqual(sum(b.available + b.reserved for b in balances), expected)
            self.assertTrue(all(b.available >= 0 and b.reserved >= 0 for b in balances))

    def test_buy_reserves_and_prevents_reusing_money(self):
        first = self.order(1, "BUY", "100", "8")
        second = self.order(1, "BUY", "100", "3")
        self.assertEqual(first.status, "open")
        self.assertEqual(second.status, "rejected")
        self.assertEqual(self.balance(1, 1).available, D(200))
        self.assertEqual(self.balance(1, 1).reserved, D(800))
        self.assertEqual(second.reserved_amount, 0)
        self.assert_conserved()

    def test_sell_reserves_and_prevents_reusing_assets(self):
        self.order(1, "SELL", "100", "8")
        rejected = self.order(1, "SELL", "100", "3")
        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(self.balance(1, 2).available, D(2))
        self.assertEqual(self.balance(1, 2).reserved, D(8))
        self.assert_conserved()

    def test_better_price_executes_before_earlier_order(self):
        expensive = self.order(2, "SELL", "105", "1")
        cheap = self.order(3, "SELL", "100", "1")
        buy = self.order(1, "BUY", "110", "1.5")
        self.assertEqual([t.sell_order_id for t in self.trades()], [cheap.id, expensive.id])
        self.assertEqual([t.price for t in self.trades()], [D(100), D(105)])
        self.assertEqual(buy.status, "filled")
        self.assertEqual(expensive.remaining_volume, D("0.5"))
        self.assertEqual(expensive.status, "partial")
        self.assertEqual(self.balance(1, 1).available, D("847.5"))
        self.assertEqual(self.balance(1, 1).reserved, D(0))
        self.assert_conserved()

    def test_equal_price_uses_time_priority(self):
        first = self.order(2, "SELL", "100", "1")
        second = self.order(3, "SELL", "100", "1")
        self.order(1, "BUY", "100", "1")
        self.assertEqual(self.trades()[0].sell_order_id, first.id)
        self.assertEqual(second.status, "open")
        self.assert_conserved()

    def test_incoming_sell_executes_at_resting_buy_price(self):
        buy = self.order(1, "BUY", "110", "2")
        sell = self.order(2, "SELL", "100", "1")
        self.assertEqual(self.trades()[0].price, D(110))
        self.assertEqual(buy.status, "partial")
        self.assertEqual(sell.status, "filled")
        self.assertEqual(buy.reserved_amount, D(110))
        self.assert_conserved()

    def test_cancelling_partial_order_returns_only_remaining_reserve(self):
        buy = self.order(1, "BUY", "110", "2")
        self.order(2, "SELL", "100", "1")
        cancel_order(self.db, 1, buy.id)
        cancel_order(self.db, 1, buy.id)
        self.assertEqual(buy.status, "cancelled")
        self.assertEqual(self.balance(1, 1).available, D(890))
        self.assertEqual(self.balance(1, 1).reserved, D(0))
        self.assertEqual(get_order_book(self.db, 1, 1)["bids"], [])
        self.assert_conserved()

    def test_books_are_separate_and_self_trades_are_skipped(self):
        self.order(1, "SELL", "100", "1")
        self.order(1, "BUY", "100", "1")
        self.order(2, "BUY", "100", "1", instrument=2)
        self.assertEqual(self.trades(), [])
        self.assertEqual(len(get_order_book(self.db, 1, 1)["bids"]), 1)
        self.assertEqual(len(get_order_book(self.db, 1, 2)["bids"]), 1)
        self.assert_conserved()

    def test_price_history_and_last_price_follow_trades(self):
        self.order(2, "SELL", "101", "1")
        self.order(1, "BUY", "102", "1")
        self.assertEqual(get_price_history(self.db, 1, 1), [D(101)])
        self.assertEqual(get_price_history(self.db, 1, 2), [])
        market = self.db.scalar(select(SimulationRunInstrument).where(
            SimulationRunInstrument.run_id == 1, SimulationRunInstrument.instrument_id == 1
        ))
        self.assertEqual(market.last_price, D(101))

    def test_rounding_and_many_partial_fills_conserve_balances(self):
        buy = self.order(1, "BUY", "0.12345678", "0.0000003")
        for _ in range(3):
            self.order(2, "SELL", "0.12345678", "0.0000001")
            self.assert_conserved()
        self.assertEqual(buy.status, "filled")
        self.assertEqual(buy.reserved_amount, 0)
        self.assertEqual(self.balance(1, 1).reserved, 0)

    def test_sub_quantum_order_value_is_rejected(self):
        with self.assertRaises(TradingError):
            self.order(1, "BUY", "0.00000001", "0.00000001")
        self.assert_conserved()

    def test_sub_quantum_partial_fill_does_not_transfer_assets_for_free(self):
        self.order(2, "SELL", "0.12345678", "0.00000011")
        self.order(1, "BUY", "0.12345678", "0.0000001")
        self.order(3, "BUY", "0.12345678", "1")
        self.assertEqual(len(self.trades()), 1)
        self.assertTrue(all(trade.quote_amount > 0 for trade in self.trades()))
        self.assert_conserved()

    def test_incoming_sell_uses_highest_bid_first(self):
        low = self.order(1, "BUY", "100", "1")
        high = self.order(3, "BUY", "110", "1")
        self.order(2, "SELL", "90", "1")
        self.assertEqual(self.trades()[0].buy_order_id, high.id)
        self.assertEqual(low.status, "open")
        self.assert_conserved()

    def test_non_crossing_orders_stay_open(self):
        self.order(1, "BUY", "99", "1")
        self.order(2, "SELL", "100", "1")
        self.assertEqual(self.trades(), [])
        self.assert_conserved()

    def test_stopped_run_cannot_accept_orders(self):
        self.run.status = "stopped"
        self.db.commit()
        with self.assertRaises(TradingError):
            self.order(1, "BUY", "100", "1")

    def test_cancel_sell_releases_remaining_base_asset(self):
        sell = self.order(2, "SELL", "100", "2")
        self.order(1, "BUY", "100", "1")
        cancel_order(self.db, 1, sell.id)
        self.assertEqual(self.balance(2, 2).available, D(9))
        self.assertEqual(self.balance(2, 2).reserved, 0)
        self.assert_conserved()

    def test_filled_orders_do_not_execute_twice(self):
        self.order(2, "SELL", "100", "1")
        self.order(1, "BUY", "100", "1")
        self.order(3, "BUY", "100", "1")
        self.assertEqual(len(self.trades()), 1)
        self.assert_conserved()

    def test_invalid_amount_and_foreign_participant_are_rejected(self):
        for price in ("0", "NaN", "Infinity", "0.000000001"):
            with self.assertRaises(TradingError):
                self.order(1, "BUY", price, "1")
        with self.assertRaises(TradingError):
            self.order(999, "BUY", "100", "1")
        self.assert_conserved()

    def test_rollback_undoes_order_trade_and_balances(self):
        self.order(2, "SELL", "100", "1")
        self.db.commit()
        self.order(1, "BUY", "100", "1")
        self.db.rollback()
        self.assertEqual(self.trades(), [])
        self.assertEqual(self.balance(1, 1).available, D(1000))
        self.assertEqual(self.balance(2, 2).reserved, D(1))
        self.assert_conserved()


if __name__ == "__main__":
    unittest.main()
