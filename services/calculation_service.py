from typing import Optional, List
from models import Trade, Instrument


def compute_max_r(
    entry_candle_size: Optional[float],
    mfe: Optional[float],
    mae_sl_buffer: Optional[float],
    instrument_sl_buffer: Optional[float],
) -> Optional[float]:
    """
    Excel formula:
    IF(L="","",IFS(D=Settings!C4, IF(K>=Settings!J4,-1, L/(J+Settings!J4)), ...))

    Where:
    - L = MFE
    - K = MAE SL BUFFER
    - J = ENTRY CANDLE SIZE
    - Settings!J = instrument.sl_buffer

    Returns None if MFE is missing.
    Returns -1 if stop hit (MAE >= planned SL buffer).
    Otherwise MFE / (entry_candle_size + sl_buffer).
    """
    if mfe is None:
        return None

    if mae_sl_buffer is not None and instrument_sl_buffer is not None:
        if mae_sl_buffer >= instrument_sl_buffer:
            return -1.0

    if entry_candle_size is None:
        return None

    risk = entry_candle_size + (instrument_sl_buffer or 0.0)
    if risk == 0:
        return None

    return mfe / risk


def compute_fixed_r_target(
    max_r: Optional[float],
    instrument_fixed_r_target: Optional[float],
) -> Optional[float]:
    """
    Excel formula:
    IFS(D=Settings!C4, IF(M>=Settings!K4, Settings!K4, -1), ...)

    Where:
    - M = MAX R
    - Settings!K = instrument.fixed_r_target

    Returns instrument.fixed_r_target if max_r >= target.
    Returns -1 otherwise (including when max_r is None).
    """
    if max_r is None or instrument_fixed_r_target is None:
        return -1.0

    if max_r >= instrument_fixed_r_target:
        return instrument_fixed_r_target

    return -1.0


def compute_portfolio_stats(trades: List[Trade]) -> List[Trade]:
    """
    Given a list of Trade objects, compute and set all derived fields
    RESET PER CALENDAR YEAR:
    - total_r (running sum of fixed_r_target within the active year)
    - is_win / is_loss
    - win_streak / loss_streak (within the year)
    - peak_r (running max of total_r within the year)
    - drawdown (total_r - peak_r within the year)
    - max_drawdown (min of drawdown within the year)

    Modifies trades in place.
    """
    from collections import defaultdict
    trades_by_year = defaultdict(list)
    for trade in trades:
        y = trade.year or (trade.entry_date.year if trade.entry_date else 0)
        trades_by_year[y].append(trade)

    for y, year_trades in trades_by_year.items():
        total_r = 0.0
        win_streak = 0
        loss_streak = 0
        peak_r = None
        max_drawdown = None

        for trade in year_trades:
            exec_status = (trade.execution_status or "LIVE").upper()

            # If trade has an explicit custom realized_r (e.g. BE, Runner, Cut Loss, Trail), use it
            if trade.realized_r is not None:
                fixed = trade.realized_r
                trade.fixed_r_target = trade.realized_r
            else:
                fixed = trade.fixed_r_target
                if fixed is None:
                    fixed = 0.0

            # Front-Run and Missed trades do not alter live account total R or live win/loss streaks
            if exec_status in ("FRONT_RUN", "MISSED"):
                trade.is_win = False
                trade.is_loss = False
                trade.win_streak = win_streak
                trade.loss_streak = loss_streak
                trade.total_r = round(total_r, 10)
                trade.peak_r = round(peak_r if peak_r is not None else 0.0, 10)
                trade.drawdown = round(drawdown if peak_r is not None else 0.0, 10)
                trade.max_drawdown = round(max_drawdown if max_drawdown is not None else 0.0, 10)
                continue

            total_r += fixed
            trade.total_r = round(total_r, 10)

            if fixed > 0:
                trade.is_win = True
                trade.is_loss = False
                win_streak += 1
                loss_streak = 0
            elif fixed < 0:
                trade.is_win = False
                trade.is_loss = True
                win_streak = 0
                loss_streak += 1
            else:
                # Break Even (0.00R)
                trade.is_win = False
                trade.is_loss = False
                win_streak = 0
                loss_streak = 0

            trade.win_streak = win_streak
            trade.loss_streak = loss_streak

            if peak_r is None or total_r > peak_r:
                peak_r = total_r
            trade.peak_r = round(peak_r, 10)

            drawdown = total_r - peak_r
            trade.drawdown = round(drawdown, 10)

            if max_drawdown is None or drawdown < max_drawdown:
                max_drawdown = drawdown
            trade.max_drawdown = round(max_drawdown, 10)

    return trades


def serialize_trade_preview(t: Trade) -> dict:
    """Helper to serialize trade data for interactive review popovers."""
    return {
        "id": t.id,
        "date": t.entry_date.strftime("%b %d, %Y") if t.entry_date else "",
        "time": t.entry_time.strftime("%I:%M %p") if t.entry_time else "",
        "pair": t.instrument_obj.name if getattr(t, 'instrument_obj', None) else "—",
        "setup": t.strategy_obj.name if getattr(t, 'strategy_obj', None) else "—",
        "prob": t.probability_level_obj.name if getattr(t, 'probability_level_obj', None) else "—",
        "r": round(t.fixed_r_target, 2) if t.fixed_r_target is not None else 0.0,
        "is_win": bool(t.is_win),
        "is_loss": bool(t.is_loss),
        "status": getattr(t, 'execution_status', 'LIVE') or 'LIVE',
        "is_swept": bool(getattr(t, 'is_sl_swept', False)),
    }


def compute_execution_outcomes(trades: List[Trade]) -> dict:
    """
    Computes breakdown of trades by Outcome Type:
    - Hit TP (Full Take Profit reached)
    - Runner / Exceeded TP
    - Break Even (0.0R)
    - Trailing Stop
    - Cut Loss
    - Full SL
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "categories": [],
            "total_trades": 0,
            "tp_count": 0,
            "runner_count": 0,
            "be_count": 0,
            "trail_count": 0,
            "cut_count": 0,
            "sl_count": 0,
        }

    outcomes = {
        "FULL_TP": {"name": "Hit Full TP", "icon": "🎯", "count": 0, "total_r": 0.0, "color": "#16a34a", "trades": []},
        "RUNNER": {"name": "Runner / Exceeded TP", "icon": "🚀", "count": 0, "total_r": 0.0, "color": "#4f46e5", "trades": []},
        "BREAK_EVEN": {"name": "Break Even (0.0R)", "icon": "⚖️", "count": 0, "total_r": 0.0, "color": "#64748b", "trades": []},
        "TRAILING_STOP": {"name": "Trailing Stop", "icon": "🛡️", "count": 0, "total_r": 0.0, "color": "#0284c7", "trades": []},
        "CUT_LOSS": {"name": "Early Cut Loss", "icon": "✂️", "count": 0, "total_r": 0.0, "color": "#ea580c", "trades": []},
        "FULL_SL": {"name": "Full Stop Loss", "icon": "❌", "count": 0, "total_r": 0.0, "color": "#dc2626", "trades": []},
    }

    for t in trades:
        otype = t.outcome_type or "AUTO"
        r = t.fixed_r_target if t.fixed_r_target is not None else 0.0

        if otype == "AUTO":
            if r > 0:
                key = "FULL_TP"
            elif r == 0:
                key = "BREAK_EVEN"
            else:
                key = "FULL_SL"
        elif otype in outcomes:
            key = otype
        else:
            key = "FULL_TP" if r > 0 else ("BREAK_EVEN" if r == 0 else "FULL_SL")

        outcomes[key]["count"] += 1
        outcomes[key]["total_r"] += r
        outcomes[key]["trades"].append(serialize_trade_preview(t))

    cat_list = []
    for k, v in outcomes.items():
        pct = (v["count"] / total_trades * 100) if total_trades else 0.0
        avg_r = (v["total_r"] / v["count"]) if v["count"] > 0 else 0.0
        cat_list.append({
            "key": k,
            "name": v["name"],
            "icon": v["icon"],
            "count": v["count"],
            "pct": round(pct, 1),
            "total_r": round(v["total_r"], 2),
            "avg_r": round(avg_r, 2),
            "color": v["color"],
            "trades_list": v["trades"],
        })

    return {
        "categories": cat_list,
        "total_trades": total_trades,
        "tp_count": outcomes["FULL_TP"]["count"],
        "runner_count": outcomes["RUNNER"]["count"],
        "be_count": outcomes["BREAK_EVEN"]["count"],
        "trail_count": outcomes["TRAILING_STOP"]["count"],
        "cut_count": outcomes["CUT_LOSS"]["count"],
        "sl_count": outcomes["FULL_SL"]["count"],
    }


def compute_psychology_stats(trades: List[Trade]) -> dict:
    """
    Computes breakdown of trader emotions before entry and after exit,
    along with Win Rates, Net Return, and Emotional Discipline Score.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "before_stats": [],
            "after_stats": [],
            "discipline_score": 100,
            "fomo_count": 0,
            "revenge_count": 0,
            "calm_count": 0,
            "total_tagged": 0,
        }

    before_map = {
        "CALM": {"name": "Calm & Disciplined", "icon": "🧘", "count": 0, "wins": 0, "total_r": 0.0, "is_good": True, "trades": []},
        "FOMO": {"name": "FOMO / Rushed", "icon": "⚡", "count": 0, "wins": 0, "total_r": 0.0, "is_good": False, "trades": []},
        "HESITANT": {"name": "Fearful / Hesitant", "icon": "😨", "count": 0, "wins": 0, "total_r": 0.0, "is_good": False, "trades": []},
        "REVENGE": {"name": "Revenge Trading", "icon": "🔥", "count": 0, "wins": 0, "total_r": 0.0, "is_good": False, "trades": []},
        "BORED": {"name": "Boredom Entry", "icon": "🥱", "count": 0, "wins": 0, "total_r": 0.0, "is_good": False, "trades": []},
        "CONFIDENT": {"name": "High Confidence", "icon": "💎", "count": 0, "wins": 0, "total_r": 0.0, "is_good": True, "trades": []},
    }

    after_map = {
        "SATISFIED": {"name": "Followed Plan", "icon": "✅", "count": 0, "wins": 0, "total_r": 0.0, "trades": []},
        "GREEDY": {"name": "Greed / Held Too Long", "icon": "🤑", "count": 0, "wins": 0, "total_r": 0.0, "trades": []},
        "PANICKED": {"name": "Panicked / Cut Early", "icon": "😱", "count": 0, "wins": 0, "total_r": 0.0, "trades": []},
        "FRUSTRATED": {"name": "Frustrated / Tilted", "icon": "😤", "count": 0, "wins": 0, "total_r": 0.0, "trades": []},
        "NEUTRAL": {"name": "Detached / Neutral", "icon": "🧘", "count": 0, "wins": 0, "total_r": 0.0, "trades": []},
    }

    total_tagged_before = 0
    good_before_count = 0

    for t in trades:
        r = t.fixed_r_target if t.fixed_r_target is not None else 0.0
        win = (r > 0)
        t_preview = serialize_trade_preview(t)

        b = (t.emotion_before or "").upper()
        if b in before_map:
            total_tagged_before += 1
            before_map[b]["count"] += 1
            if win:
                before_map[b]["wins"] += 1
            before_map[b]["total_r"] += r
            before_map[b]["trades"].append(t_preview)
            if before_map[b]["is_good"]:
                good_before_count += 1

        a = (t.emotion_after or "").upper()
        if a in after_map:
            after_map[a]["count"] += 1
            if win:
                after_map[a]["wins"] += 1
            after_map[a]["total_r"] += r
            after_map[a]["trades"].append(t_preview)

    before_list = []
    for k, v in before_map.items():
        if v["count"] > 0:
            wr = (v["wins"] / v["count"] * 100) if v["count"] else 0.0
            before_list.append({
                "key": k,
                "name": v["name"],
                "icon": v["icon"],
                "count": v["count"],
                "win_rate": round(wr, 1),
                "total_r": round(v["total_r"], 2),
                "is_good": v["is_good"],
                "trades_list": v["trades"],
            })
    before_list.sort(key=lambda x: x["count"], reverse=True)

    after_list = []
    for k, v in after_map.items():
        if v["count"] > 0:
            wr = (v["wins"] / v["count"] * 100) if v["count"] else 0.0
            after_list.append({
                "key": k,
                "name": v["name"],
                "icon": v["icon"],
                "count": v["count"],
                "win_rate": round(wr, 1),
                "total_r": round(v["total_r"], 2),
                "trades_list": v["trades"],
            })
    after_list.sort(key=lambda x: x["count"], reverse=True)

    discipline_score = round((good_before_count / total_tagged_before * 100), 1) if total_tagged_before > 0 else 100.0

    return {
        "before_stats": before_list,
        "after_stats": after_list,
        "discipline_score": discipline_score,
        "fomo_count": before_map["FOMO"]["count"],
        "revenge_count": before_map["REVENGE"]["count"],
        "calm_count": before_map["CALM"]["count"],
        "total_tagged": total_tagged_before,
    }


def compute_execution_status_stats(trades: List[Trade]) -> dict:
    """
    Computes breakdown of Live Executed vs Front-Run vs Missed Trades,
    along with Opportunity Cost and Execution Efficiency.
    """
    total_trades = len(trades)
    if total_trades == 0:
        return {
            "live_count": 0,
            "front_run_count": 0,
            "missed_count": 0,
            "sl_swept_count": 0,
            "live_r": 0.0,
            "front_run_missed_r": 0.0,
            "missed_trade_r": 0.0,
            "sl_swept_lost_r": 0.0,
            "total_missed_r": 0.0,
            "theoretical_r": 0.0,
            "execution_rate": 100.0,
            "tags_summary": [],
        }

    live_trades = []
    front_run_trades = []
    missed_trades = []
    sl_swept_trades = []

    live_r = 0.0
    front_run_r = 0.0
    missed_r = 0.0
    sl_swept_lost_r = 0.0

    for t in trades:
        st = (t.execution_status or "LIVE").upper()
        # Potential / fixed R of the setup
        r = t.fixed_r_target if t.fixed_r_target is not None else 0.0

        if getattr(t, 'is_sl_swept', False):
            sl_swept_trades.append(t)
            if r < 0:
                sl_swept_lost_r += abs(r)

        if st == "FRONT_RUN":
            front_run_trades.append(t)
            if r > 0:
                front_run_r += r
        elif st == "MISSED":
            missed_trades.append(t)
            if r > 0:
                missed_r += r
        else:
            # LIVE
            live_trades.append(t)
            live_r += r

    total_missed_potential = front_run_r + missed_r
    theoretical_r = live_r + total_missed_potential
    exec_rate = round((len(live_trades) / total_trades * 100), 1) if total_trades else 100.0

    tags_summary = [
        {
            "key": "MISSED",
            "name": "Missed Trade",
            "icon": "⚪",
            "desc": "Valid setup, not entered (hesitated/late)",
            "count": len(missed_trades),
            "impact_r": round(missed_r, 2),
            "impact_type": "missed",
            "trades_list": [serialize_trade_preview(t) for t in missed_trades],
        },
        {
            "key": "FRONT_RUN",
            "name": "Front-Run (Unfilled)",
            "icon": "🟡",
            "desc": "Limit order missed by 1-2 ticks",
            "count": len(front_run_trades),
            "impact_r": round(front_run_r, 2),
            "impact_type": "missed",
            "trades_list": [serialize_trade_preview(t) for t in front_run_trades],
        },
        {
            "key": "SL_SWEPT",
            "name": "SL Swept / Tapped",
            "icon": "🪤",
            "desc": "Stopped out then moved to target",
            "count": len(sl_swept_trades),
            "impact_r": round(sl_swept_lost_r, 2),
            "impact_type": "lost",
            "trades_list": [serialize_trade_preview(t) for t in sl_swept_trades],
        },
    ]

    return {
        "live_count": len(live_trades),
        "front_run_count": len(front_run_trades),
        "missed_count": len(missed_trades),
        "sl_swept_count": len(sl_swept_trades),
        "live_r": round(live_r, 2),
        "front_run_missed_r": round(front_run_r, 2),
        "missed_trade_r": round(missed_r, 2),
        "sl_swept_lost_r": round(sl_swept_lost_r, 2),
        "total_missed_r": round(total_missed_potential, 2),
        "theoretical_r": round(theoretical_r, 2),
        "execution_rate": exec_rate,
        "tags_summary": tags_summary,
        "front_run_trades": front_run_trades,
        "missed_trades": missed_trades,
        "sl_swept_trades": sl_swept_trades,
    }



