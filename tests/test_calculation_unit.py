import pytest
from services.calculation_service import (
    compute_max_r,
    compute_fixed_r_target,
    compute_portfolio_stats,
    serialize_trade_preview,
)
from models import Trade, Instrument
from datetime import date


class TestComputeMaxR:
    def test_valid_values_returns_correct_r(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=0.06,
            mae_sl_buffer=None,
            instrument_sl_buffer=0.5,
        )
        assert result == pytest.approx(0.06 / (0.02 + 0.5), rel=1e-5)

    def test_none_mfe_returns_none(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=None,
            mae_sl_buffer=None,
            instrument_sl_buffer=0.5,
        )
        assert result is None

    def test_zero_entry_candle_size_returns_none(self):
        result = compute_max_r(
            entry_candle_size=None,
            mfe=0.06,
            mae_sl_buffer=None,
            instrument_sl_buffer=0.5,
        )
        assert result is None

    def test_mae_sl_swept_returns_negative_one(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=0.001,
            mae_sl_buffer=0.5,
            instrument_sl_buffer=0.4,
        )
        assert result == -1.0

    def test_mae_sl_buffer_equals_instrument_sl_buffer_returns_negative_one(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=0.001,
            mae_sl_buffer=0.4,
            instrument_sl_buffer=0.4,
        )
        assert result == -1.0

    def test_all_none_values_returns_none(self):
        result = compute_max_r(
            entry_candle_size=None,
            mfe=None,
            mae_sl_buffer=None,
            instrument_sl_buffer=0.5,
        )
        assert result is None

    def test_zero_instrument_sl_buffer_works(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=0.06,
            mae_sl_buffer=None,
            instrument_sl_buffer=0.0,
        )
        assert result == pytest.approx(0.06 / 0.02, rel=1e-5)

    def test_negative_mae_sl_buffer_not_swept(self):
        result = compute_max_r(
            entry_candle_size=0.02,
            mfe=0.06,
            mae_sl_buffer=-0.1,
            instrument_sl_buffer=0.5,
        )
        assert result == pytest.approx(0.06 / (0.02 + 0.5), rel=1e-5)


class TestComputeFixedRTarget:
    def test_max_r_exceeds_target_returns_target(self):
        result = compute_fixed_r_target(max_r=4.0, instrument_fixed_r_target=3.3)
        assert result == 3.3

    def test_max_r_below_target_returns_negative_one(self):
        result = compute_fixed_r_target(max_r=2.0, instrument_fixed_r_target=3.3)
        assert result == -1.0

    def test_max_r_equals_target_returns_target(self):
        result = compute_fixed_r_target(max_r=3.3, instrument_fixed_r_target=3.3)
        assert result == 3.3

    def test_none_max_r_returns_negative_one(self):
        result = compute_fixed_r_target(max_r=None, instrument_fixed_r_target=3.3)
        assert result == -1.0

    def test_none_instrument_target_returns_negative_one(self):
        result = compute_fixed_r_target(max_r=4.0, instrument_fixed_r_target=None)
        assert result == -1.0

    def test_both_none_returns_negative_one(self):
        result = compute_fixed_r_target(max_r=None, instrument_fixed_r_target=None)
        assert result == -1.0

    def test_zero_max_r_returns_negative_one(self):
        result = compute_fixed_r_target(max_r=0.0, instrument_fixed_r_target=3.3)
        assert result == -1.0


class TestComputePortfolioStats:
    def test_empty_trades_list_returns_empty(self):
        result = compute_portfolio_stats([])
        assert result == []

    def test_single_win_trade_stats(self):
        trade = Trade(
            id=1,
            entry_date=date(2026, 1, 15),
            direction="LONG",
            execution_status="LIVE",
            fixed_r_target=3.3,
            realized_r=3.3,
        )
        result = compute_portfolio_stats([trade])
        assert result[0].total_r == 3.3
        assert result[0].is_win is True
        assert result[0].is_loss is False
        assert result[0].win_streak == 1
        assert result[0].loss_streak == 0

    def test_single_loss_trade_stats(self):
        trade = Trade(
            id=2,
            entry_date=date(2026, 1, 16),
            direction="LONG",
            execution_status="LIVE",
            fixed_r_target=-1.0,
            realized_r=-1.0,
        )
        result = compute_portfolio_stats([trade])
        assert result[0].total_r == -1.0
        assert result[0].is_win is False
        assert result[0].is_loss is True
        assert result[0].win_streak == 0
        assert result[0].loss_streak == 1

    def test_earnings_loss_streak(self):
        trades = [
            Trade(
                id=1,
                entry_date=date(2026, 1, 15),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=3.3,
                realized_r=3.3,
            ),
            Trade(
                id=2,
                entry_date=date(2026, 1, 16),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=3.3,
                realized_r=3.3,
            ),
            Trade(
                id=3,
                entry_date=date(2026, 1, 17),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=-1.0,
                realized_r=-1.0,
            ),
            Trade(
                id=4,
                entry_date=date(2026, 1, 18),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=-1.0,
                realized_r=-1.0,
            ),
            Trade(
                id=5,
                entry_date=date(2026, 1, 19),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=-1.0,
                realized_r=-1.0,
            ),
        ]
        result = compute_portfolio_stats(trades)
        assert result[4].win_streak == 0
        assert result[4].loss_streak == 3

    def test_break_even_no_color(self):
        trade = Trade(
            id=10,
            entry_date=date(2026, 1, 15),
            direction="LONG",
            execution_status="LIVE",
            fixed_r_target=0.0,
            realized_r=0.0,
        )
        result = compute_portfolio_stats([trade])
        assert result[0].is_win is False
        assert result[0].is_loss is False
        assert result[0].total_r == 0.0

    def test_front_run_doesnt_affect_stats(self):
        trades = [
            Trade(
                id=1,
                entry_date=date(2026, 1, 15),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=3.3,
                realized_r=3.3,
            ),
            Trade(
                id=2,
                entry_date=date(2026, 1, 16),
                direction="LONG",
                execution_status="MISSED",
                fixed_r_target=3.3,
                realized_r=3.3,
            ),
        ]
        result = compute_portfolio_stats(trades)
        assert result[1].is_win is False
        assert result[1].is_loss is False
        assert result[1].total_r == 3.3

    def test_missed_doesnt_affect_stats(self):
        trades = [
            Trade(
                id=1,
                entry_date=date(2026, 1, 15),
                direction="LONG",
                execution_status="LIVE",
                fixed_r_target=3.3,
                realized_r=3.3,
            ),
            Trade(
                id=2,
                entry_date=date(2026, 1, 16),
                direction="LONG",
                execution_status="MISSED",
                fixed_r_target=2.0,
                realized_r=2.0,
            ),
        ]
        result = compute_portfolio_stats(trades)
        assert result[1].total_r == 3.3


class TestSerializeTradePreview:
    def test_basic_serialization(self):
        from models import Strategy, ProbabilityLevel
        from database import SessionLocal
        
        with SessionLocal() as db:
            strategy = db.query(Strategy).first()
            prob = db.query(ProbabilityLevel).first()
            
            trade = Trade(
                id=100,
                entry_date=date(2026, 1, 15),
                entry_time=None,
                fixed_r_target=2.5,
                is_win=True,
                is_loss=False,
                execution_status="LIVE",
                is_sl_swept=False,
            )
            trade.instrument_obj = Instrument(name="BTCUSD", slug="btcusd", sl_buffer=0.0, fixed_r_target=3.0)
            if strategy:
                trade.strategy_obj = strategy
            if prob:
                trade.probability_level_obj = prob

        result = serialize_trade_preview(trade)
        assert result["id"] == 100
        assert result["r"] == 2.5
        assert result["is_win"] is True
        assert result["is_loss"] is False
        assert result["status"] == "LIVE"
        assert result["is_swept"] is False

    def test_false_values_serialized_correctly(self):
        trade = Trade(id=101, is_win=False, is_loss=False)
        result = serialize_trade_preview(trade)
        assert result["is_win"] is False
        assert result["is_loss"] is False