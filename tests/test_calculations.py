import sys
sys.path.insert(0, r"D:\Web Development\Trading Journal")

from database import SessionLocal
from models import Trade
from services.calculation_service import (
    compute_max_r,
    compute_fixed_r_target,
    compute_portfolio_stats,
)


def test_calculations():
    with SessionLocal() as db:
        trades = db.query(Trade).order_by(Trade.id).limit(10).all()
        # Eager load instruments
        for t in trades:
            _ = t.instrument_obj  # trigger lazy load while session is open

    print(f"Testing first {len(trades)} trades...\n")

    errors = []
    for trade in trades:
        inst = trade.instrument_obj
        computed_max_r = compute_max_r(
            trade.entry_candle_size,
            trade.mfe,
            trade.mae_sl_buffer,
            inst.sl_buffer if inst else None,
        )
        computed_fixed = compute_fixed_r_target(
            computed_max_r,
            inst.fixed_r_target if inst else None,
        )

        # Compare with cached Excel values
        # Edge case: Excel sometimes caches -1 when MFE/MAE is '-' (string dash).
        # Our formula returns None for missing MFE. Accept both as equivalent edge cases.
        edge_case_max_r = (
            trade.mfe is None
            and trade.max_r == -1.0
            and computed_max_r is None
        )

        if not edge_case_max_r:
            if trade.max_r is not None and computed_max_r is not None:
                if abs(trade.max_r - computed_max_r) > 0.0001:
                    errors.append(
                        f"Trade {trade.id}: MAX R mismatch | Excel: {trade.max_r} | Computed: {computed_max_r:.6f}"
                    )
            elif trade.max_r != computed_max_r:
                errors.append(
                    f"Trade {trade.id}: MAX R mismatch | Excel: {trade.max_r} | Computed: {computed_max_r}"
                )

        if trade.fixed_r_target is not None and computed_fixed is not None:
            if abs(trade.fixed_r_target - computed_fixed) > 0.0001:
                errors.append(
                    f"Trade {trade.id}: FIXED R mismatch | Excel: {trade.fixed_r_target} | Computed: {computed_fixed:.6f}"
                )
        elif trade.fixed_r_target != computed_fixed:
            errors.append(
                f"Trade {trade.id}: FIXED R mismatch | Excel: {trade.fixed_r_target} | Computed: {computed_fixed}"
            )

    if errors:
        print(f"[FAIL] {len(errors)} discrepancies found:\n")
        for e in errors:
            print(f"  {e}")
    else:
        print("[PASS] All 10 trades match Excel cached values exactly (+-0.0001).")

    # Now test portfolio stats on the full set
    with SessionLocal() as db:
        all_trades = db.query(Trade).order_by(Trade.id).all()
        for t in all_trades:
            _ = t.instrument_obj

    # Reset derived fields to recompute
    for t in all_trades:
        t.total_r = None
        t.is_win = None
        t.is_loss = None
        t.win_streak = None
        t.loss_streak = None
        t.peak_r = None
        t.drawdown = None
        t.max_drawdown = None

    compute_portfolio_stats(all_trades)

    # Compare first 10
    stat_errors = []
    with SessionLocal() as db:
        cached = db.query(Trade).order_by(Trade.id).limit(10).all()

    for i, t in enumerate(all_trades[:10]):
        c = cached[i]
        checks = [
            ("total_r", c.total_r, t.total_r, 0.0001),
            ("is_win", c.is_win, t.is_win, None),
            ("is_loss", c.is_loss, t.is_loss, None),
            ("win_streak", c.win_streak, t.win_streak, None),
            ("loss_streak", c.loss_streak, t.loss_streak, None),
            ("peak_r", c.peak_r, t.peak_r, 0.0001),
            ("drawdown", c.drawdown, t.drawdown, 0.0001),
            ("max_drawdown", c.max_drawdown, t.max_drawdown, 0.0001),
        ]
        for name, excel_val, comp_val, tol in checks:
            # Skip comparison if Excel has no value (formula not filled down in sheet)
            if excel_val is None:
                continue
            if tol is not None:
                if comp_val is not None:
                    if abs(excel_val - comp_val) > tol:
                        stat_errors.append(
                            f"Trade {t.id}: {name} | Excel: {excel_val} | Computed: {comp_val}"
                        )
                else:
                    stat_errors.append(
                        f"Trade {t.id}: {name} | Excel: {excel_val} | Computed: {comp_val}"
                    )
            else:
                if excel_val != comp_val:
                    stat_errors.append(
                        f"Trade {t.id}: {name} | Excel: {excel_val} | Computed: {comp_val}"
                    )

    if stat_errors:
        print(f"\n[FAIL] {len(stat_errors)} portfolio stat discrepancies:\n")
        for e in stat_errors:
            print(f"  {e}")
    else:
        print("[PASS] Portfolio stats (first 10) match Excel cached values exactly.")

    if not errors and not stat_errors:
        print("\n[OK] Phase 2 Calculation Engine validated successfully.")
        return True
    return False


if __name__ == "__main__":
    ok = test_calculations()
    sys.exit(0 if ok else 1)
