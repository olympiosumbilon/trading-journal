import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import func
from database import SessionLocal
from models import Trade, Instrument, Session, Strategy


def export_trades_csv() -> str:
    """Export all trades to CSV format."""
    from sqlalchemy.orm import selectinload
    with SessionLocal() as db:
        trades = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
            )
            .order_by(Trade.id)
            .all()
        )

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "ID", "Date", "Time", "Session", "Instrument", "Setup",
        "Probability", "MTF Phase", "Entry News", "Management News",
        "Entry Candle", "MAE Buffer", "MFE", "Max R", "Fixed R Target",
        "Total R", "Is Win", "Is Loss", "Win Streak", "Loss Streak",
        "Peak R", "Drawdown", "Max Drawdown", "Comments",
    ])

    for t in trades:
        writer.writerow([
            t.id,
            t.entry_date,
            t.entry_time,
            t.session_obj.name if t.session_obj else "",
            t.instrument_obj.name if t.instrument_obj else "",
            t.strategy_obj.name if t.strategy_obj else "",
            t.probability_level_obj.name if t.probability_level_obj else "",
            t.mtf_phase_obj.name if t.mtf_phase_obj else "",
            t.entry_news or "",
            t.management_news or "",
            t.entry_candle_size,
            t.mae_sl_buffer,
            t.mfe,
            t.max_r,
            t.fixed_r_target,
            t.total_r,
            "Yes" if t.is_win else "No",
            "Yes" if t.is_loss else "No",
            t.win_streak or 0,
            t.loss_streak or 0,
            t.peak_r,
            t.drawdown,
            t.max_drawdown,
            t.comments or "",
        ])

    return output.getvalue()


def generate_weekly_report() -> dict:
    """Generate a weekly performance report (last 7 days)."""
    from sqlalchemy.orm import selectinload
    with SessionLocal() as db:
        today = datetime.now().date()
        week_ago = today - timedelta(days=7)

        trades = (
            db.query(Trade)
            .options(
                selectinload(Trade.instrument_obj),
                selectinload(Trade.session_obj),
                selectinload(Trade.strategy_obj),
            )
            .filter(Trade.entry_date >= week_ago)
            .order_by(Trade.entry_date)
            .all()
        )

        wins = sum(1 for t in trades if t.is_win)
        losses = sum(1 for t in trades if t.is_loss)
        total_r = sum(t.fixed_r_target or 0 for t in trades)

        # Per-instrument this week — build dict inside session
        inst_stats = {}
        for t in trades:
            name = t.instrument_obj.name if t.instrument_obj else "Unknown"
            if name not in inst_stats:
                inst_stats[name] = {"trades": 0, "total_r": 0.0, "wins": 0}
            inst_stats[name]["trades"] += 1
            inst_stats[name]["total_r"] += t.fixed_r_target or 0
            if t.is_win:
                inst_stats[name]["wins"] += 1

        # Serialize trades to plain dicts to avoid DetachedInstanceError after session closes
        trades_data = [
            {
                "id": t.id,
                "entry_date": t.entry_date,
                "entry_time": t.entry_time,
                "instrument": t.instrument_obj.name if t.instrument_obj else "",
                "session": t.session_obj.name if t.session_obj else "",
                "strategy": t.strategy_obj.name if t.strategy_obj else "",
                "fixed_r_target": t.fixed_r_target,
                "total_r": t.total_r,
                "is_win": t.is_win,
                "is_loss": t.is_loss,
            }
            for t in trades
        ]

        period = f"{week_ago} to {today}"
        total_trades = len(trades)

    return {
        "period": period,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total_trades * 100, 1) if total_trades else 0,
        "total_r": round(total_r, 2),
        "avg_r": round(total_r / total_trades, 2) if total_trades else 0,
        "per_instrument": inst_stats,
        "trades": trades_data,
    }


def check_alerts() -> list:
    """Check for alert conditions and return list of alert messages."""
    alerts = []

    with SessionLocal() as db:
        # Check max drawdown threshold
        max_dd = db.query(func.min(Trade.max_drawdown)).scalar()
        if max_dd is not None and max_dd < -3.0:
            alerts.append(
                f"ALERT: Max drawdown ({max_dd:.1f}R) exceeded -3R threshold. Consider reducing size or taking a break."
            )

        # Check loss streak
        recent = (
            db.query(Trade)
            .order_by(Trade.id.desc())
            .limit(5)
            .all()
        )
        loss_streak = 0
        for t in recent:
            if t.is_loss:
                loss_streak += 1
            else:
                break

        if loss_streak >= 3:
            alerts.append(
                f"ALERT: {loss_streak} consecutive losses detected. Review setups and risk management."
            )

        # Check win streak (overtrading warning)
        win_streak = 0
        for t in recent:
            if t.is_win:
                win_streak += 1
            else:
                break

        if win_streak >= 5:
            alerts.append(
                f"WARNING: {win_streak} consecutive wins. Don't get overconfident — stick to your plan."
            )

        # Check if total R is negative overall
        total_r = db.query(func.sum(Trade.fixed_r_target)).scalar() or 0
        if total_r < 0:
            alerts.append(
                f"ALERT: Overall performance is negative ({total_r:.1f}R). Review strategy and execution."
            )

    return alerts
