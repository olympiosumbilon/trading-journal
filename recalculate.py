import sys
sys.path.insert(0, r"D:\Web Development\Trading Journal")

from database import SessionLocal
from models import Trade
from services.calculation_service import (
    compute_max_r,
    compute_fixed_r_target,
    compute_portfolio_stats,
)


def recalculate_all():
    with SessionLocal() as db:
        # Eager load instruments
        trades = (
            db.query(Trade)
            .order_by(Trade.id)
            .all()
        )
        for t in trades:
            _ = t.instrument_obj

        print(f"Recalculating {len(trades)} trades...")

        for t in trades:
            inst = t.instrument_obj
            t.max_r = compute_max_r(
                t.entry_candle_size,
                t.mfe,
                t.mae_sl_buffer,
                inst.sl_buffer if inst else None,
            )
            t.fixed_r_target = compute_fixed_r_target(
                t.max_r,
                inst.fixed_r_target if inst else None,
            )

        # Reset derived fields
        for t in trades:
            t.total_r = None
            t.is_win = None
            t.is_loss = None
            t.win_streak = None
            t.loss_streak = None
            t.peak_r = None
            t.drawdown = None
            t.max_drawdown = None

        compute_portfolio_stats(trades)

        db.commit()
        print(f"Updated {len(trades)} trades with recalculated values.")


if __name__ == "__main__":
    recalculate_all()
