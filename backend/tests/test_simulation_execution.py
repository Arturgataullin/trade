import unittest
from decimal import Decimal as D
from unittest.mock import patch

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models import Order, SimulationParticipant, SimulationRun, Trade
from backend.app.services.simulation_execution import execute_step, process_next_run
from backend.app.services.simulation_results import calculate_results, get_owned_run
from backend.app.services.simulation_runs import stop_simulation
from backend.app.services.simulations import SimulationNotFoundError
from backend.tests import test_trading as trading_fixture


class SimulationExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = trading_fixture.TradingTests()
        self.fixture.setUp()
        self.db = self.fixture.db
        self.factory = sessionmaker(bind=self.fixture.engine, autoflush=False)
        run = self.fixture.run
        run.engine_version = "2"
        run.total_steps = 3
        run.configuration_snapshot = {
            "test_initial_quote_balance": 1000,
            "instrument_configs": [
                {"instrument_id": i, "test_initial_base_balance": 10}
                for i in (1, 2)
            ],
        }
        for p in self.db.scalars(select(SimulationParticipant)):
            p.participant_type = "test" if p.id == 3 else "background"
            p.min_order_volume = D(1)
            p.max_order_volume = D(1)
            p.strategy_parameters = {
                "buy_probability": 0 if p.id == 2 else 100,
                "sell_probability": 100 if p.id == 2 else 0,
                "hold_probability": 0,
                "price_deviation_pct": 0,
            }
        self.db.commit()

    def tearDown(self):
        self.fixture.tearDown()

    def run_all(self):
        while process_next_run(self.factory):
            pass
        self.db.expire_all()

    def fingerprint(self):
        self.db.expire_all()
        participants = {
            p.id: p.sequence_number for p in self.db.scalars(select(SimulationParticipant))
        }
        orders = list(self.db.scalars(select(Order).order_by(Order.sequence_number)))
        trades = list(self.db.scalars(select(Trade).order_by(Trade.sequence_number)))
        return (
            [(participants[o.participant_id], o.instrument_id, o.step, o.side,
              o.price, o.volume, o.status, o.remaining_volume) for o in orders],
            [(t.instrument_id, t.step, t.price, t.volume, t.quote_amount) for t in trades],
            [p.rng_state for p in self.db.scalars(
                select(SimulationParticipant).order_by(SimulationParticipant.sequence_number)
            )],
        )

    def test_full_run_finishes_and_releases_all_reserves(self):
        self.run_all()
        run = self.db.get(SimulationRun, 1)
        self.assertEqual(run.status, "completed")
        self.assertEqual(run.current_step, 3)
        self.assertIsNotNone(run.finished_at)
        self.assertGreater(self.db.scalar(select(func.count(Trade.id))), 0)
        self.assertEqual(self.db.scalar(select(func.count(Order.id)).where(
            Order.status.in_(("open", "partial"))
        )), 0)
        for p in (1, 2, 3):
            for asset in (1, 2, 3):
                self.assertEqual(self.fixture.balance(p, asset).reserved, 0)
        self.fixture.assert_conserved()

    def test_step_uses_previous_participants_trades_immediately(self):
        execute_step(self.db, 1)
        self.db.commit()
        orders = list(self.db.scalars(select(Order).order_by(Order.sequence_number)))
        self.assertEqual([o.participant_id for o in orders], [1, 1, 2, 2, 3, 3])
        self.assertEqual(orders[0].status, "filled")
        self.assertEqual(orders[2].status, "filled")
        self.assertEqual(orders[4].status, "open")

    def test_rollback_restores_rng_progress_orders_and_balances(self):
        execute_step(self.db, 1)
        self.db.rollback()
        self.assertEqual(self.db.get(SimulationRun, 1).current_step, 0)
        self.assertEqual(list(self.db.scalars(select(Order))), [])
        self.assertTrue(all(p.rng_state is None for p in self.db.scalars(
            select(SimulationParticipant)
        )))
        self.fixture.assert_conserved()

    def test_replay_and_resume_from_new_sessions_are_reproducible(self):
        # Variable volume and deviation exercise continued streams, not just BUY/SELL.
        for p in self.db.scalars(select(SimulationParticipant)):
            p.max_order_volume = D(2)
            p.strategy_parameters = {
                "buy_probability": 40, "sell_probability": 40,
                "hold_probability": 20, "price_deviation_pct": 1,
            }
        self.db.commit()
        self.run_all()
        first = self.fingerprint()
        self.tearDown()
        self.setUp()
        for p in self.db.scalars(select(SimulationParticipant)):
            p.max_order_volume = D(2)
            p.strategy_parameters = {
                "buy_probability": 40, "sell_probability": 40,
                "hold_probability": 20, "price_deviation_pct": 1,
            }
        self.db.commit()
        self.assertTrue(process_next_run(self.factory))
        # Every call uses a new session and reloads persisted random state.
        self.db.close()
        self.db = self.fixture.db = Session(self.fixture.engine, autoflush=False)
        self.run_all()
        self.assertEqual(first, self.fingerprint())

    def test_stop_preserves_last_committed_step_and_releases_reserves(self):
        process_next_run(self.factory)
        self.db.expire_all()
        stopped = stop_simulation(self.db, 1, 1)
        self.assertEqual(stopped.status, "stopped")
        self.assertEqual(stopped.current_step, 1)
        self.assertFalse(process_next_run(self.factory))
        self.fixture.assert_conserved()
        for p in (1, 2, 3):
            for asset in (1, 2, 3):
                self.assertEqual(self.fixture.balance(p, asset).reserved, 0)

    def test_failure_rolls_back_only_failed_step_and_cancels_open_orders(self):
        process_next_run(self.factory)
        with patch("backend.app.services.simulation_execution.decide", side_effect=RuntimeError("test")):
            with self.assertLogs("backend.app.services.simulation_execution", level="ERROR"):
                process_next_run(self.factory)
        self.db.expire_all()
        run = self.db.get(SimulationRun, 1)
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.current_step, 1)
        self.assertIsNotNone(run.error_message)
        self.assertEqual(self.db.scalar(select(func.count(Order.id)).where(
            Order.status.in_(("open", "partial"))
        )), 0)
        self.fixture.assert_conserved()

    def test_results_value_assets_and_report_trades(self):
        self.run_all()
        result = calculate_results(self.db, self.db.get(SimulationRun, 1))
        self.assertEqual(result.initial_portfolio_value, D(3000))
        self.assertEqual(result.portfolio_value, D(3000))
        self.assertEqual(result.profit, 0)
        self.assertEqual(result.return_pct, 0)
        self.assertGreater(result.trade_count, 0)
        self.assertGreater(result.test_trade_count, 0)

    def test_no_access_to_other_owners_run(self):
        with self.assertRaises(SimulationNotFoundError):
            get_owned_run(self.db, 1, 999)
        with self.assertRaises(SimulationNotFoundError):
            get_owned_run(self.db, 1, 1, run_id=999)

    def test_results_include_reserved_assets_and_zero_initial_value(self):
        execute_step(self.db, 1)
        self.db.commit()
        result = calculate_results(self.db, self.db.get(SimulationRun, 1))
        self.assertEqual(result.portfolio_value, D(3000))
        run = self.db.get(SimulationRun, 1)
        run.configuration_snapshot = {
            "test_initial_quote_balance": 0,
            "instrument_configs": [
                {"instrument_id": i, "test_initial_base_balance": 0} for i in (1, 2)
            ],
        }
        result = calculate_results(self.db, run)
        self.assertIsNone(result.return_pct)

    def test_trend_does_not_treat_initial_price_as_a_trade(self):
        for p in self.db.scalars(select(SimulationParticipant)):
            p.strategy_type = "trend_following"
            p.strategy_parameters = {"trend_window": 1, "trend_threshold_pct": 1}
        self.db.commit()
        self.run_all()
        self.assertEqual(list(self.db.scalars(select(Order))), [])
        self.assertEqual(self.db.get(SimulationRun, 1).status, "completed")


if __name__ == "__main__":
    unittest.main()
