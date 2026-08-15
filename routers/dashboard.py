from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import selectinload
from database import SessionLocal
from models import Trade, Session, Instrument, Strategy, ProbabilityLevel, MTFPhase
from services.automation_service import check_alerts
from services.calculation_service import compute_execution_outcomes, compute_psychology_stats, compute_execution_status_stats, compute_fear_greed_matrix
from utils.template_helpers import format_time_12h
from datetime import time

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["time_12h"] = format_time_12h

DAYS_MAP = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}


@router.get("/")
def dashboard(request: Request, year: str = ""):
    cookie_year = request.cookies.get("active_year", "")
    active_year_str = year.strip() if year else (cookie_year.strip() if cookie_year else "")

    with SessionLocal() as db:
        q_trades = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
            )
        )

        if active_year_str and active_year_str != "all":
            try:
                y_int = int(active_year_str)
                q_trades = q_trades.filter(Trade.year == y_int)
            except ValueError:
                pass

        trades_list = q_trades.order_by(Trade.entry_date.asc(), Trade.entry_time.asc(), Trade.id.asc()).all()

        total_trades = len(trades_list)
        wins = sum(1 for t in trades_list if t.is_win)
        losses = sum(1 for t in trades_list if t.is_loss)
        total_r = sum(t.fixed_r_target or 0.0 for t in trades_list)
        win_rate = (wins / total_trades * 100) if total_trades else 0.0

        win_rs = [t.fixed_r_target for t in trades_list if t.is_win and t.fixed_r_target is not None]
        loss_rs = [t.fixed_r_target for t in trades_list if t.is_loss and t.fixed_r_target is not None]
        avg_winner = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
        avg_loser = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0
        avg_r = (total_r / total_trades) if total_trades else 0.0

        total_win_r = sum(win_rs)
        total_loss_r = abs(sum(loss_rs))
        profit_factor = (total_win_r / total_loss_r) if total_loss_r > 0 else (total_win_r if total_win_r > 0 else 0.0)

        win_prob = wins / total_trades if total_trades else 0.0
        loss_prob = losses / total_trades if total_trades else 0.0
        expectancy = (win_prob * avg_winner) + (loss_prob * avg_loser)

        # Streaks & Drawdown
        max_win_streak = 0
        max_loss_streak = 0
        curr_win = 0
        curr_loss = 0
        peak_r = 0.0
        max_dd = 0.0
        running_r = 0.0

        for t in trades_list:
            r = t.fixed_r_target or 0.0
            running_r += r
            if running_r > peak_r:
                peak_r = running_r
            dd = running_r - peak_r
            if dd < max_dd:
                max_dd = dd

            if t.is_win:
                curr_win += 1
                curr_loss = 0
                if curr_win > max_win_streak:
                    max_win_streak = curr_win
            elif t.is_loss:
                curr_loss += 1
                curr_win = 0
                if curr_loss > max_loss_streak:
                    max_loss_streak = curr_loss

        # 1. Coin / Instrument Profitability Ranking
        instruments = db.query(Instrument).all()
        coin_rankings = []
        for inst in instruments:
            i_trades = [t for t in trades_list if t.instrument_id == inst.id]
            if i_trades:
                i_wins = sum(1 for t in i_trades if t.is_win)
                i_r = sum(t.fixed_r_target or 0.0 for t in i_trades)
                i_sr = (i_wins / len(i_trades) * 100) if i_trades else 0.0
                i_best = max([t.fixed_r_target or 0.0 for t in i_trades]) if i_trades else 0.0
                share = (i_r / total_r * 100) if total_r > 0 else 0.0
                coin_rankings.append({
                    "name": inst.name,
                    "trades": len(i_trades),
                    "wins": i_wins,
                    "losses": len(i_trades) - i_wins,
                    "win_rate": round(i_sr, 1),
                    "total_r": round(i_r, 2),
                    "best_r": round(i_best, 2),
                    "profit_share": round(share, 1),
                })
        coin_rankings.sort(key=lambda x: (x["total_r"], x["win_rate"]), reverse=True)

        # 2. Strategy & Setup Edge Leaderboard
        strategies = db.query(Strategy).all()
        strat_rankings = []
        for st in strategies:
            st_trades = [t for t in trades_list if t.strategy_id == st.id]
            if st_trades:
                st_wins = sum(1 for t in st_trades if t.is_win)
                st_r = sum(t.fixed_r_target or 0.0 for t in st_trades)
                st_sr = (st_wins / len(st_trades) * 100) if st_trades else 0.0
                strat_rankings.append({
                    "name": st.name,
                    "trades": len(st_trades),
                    "wins": st_wins,
                    "losses": len(st_trades) - st_wins,
                    "win_rate": round(st_sr, 1),
                    "total_r": round(st_r, 2),
                })
        strat_rankings.sort(key=lambda x: (x["total_r"], x["win_rate"]), reverse=True)

        # 3. Best Time Windows (30-min PHT intervals)
        time_buckets = []
        for h in range(24):
            time_buckets.append((h, 0))
            time_buckets.append((h, 30))

        time_rankings = []
        for b_h, b_m in time_buckets:
            t_matching = [
                t for t in trades_list 
                if t.entry_time and t.entry_time.hour == b_h and 
                ((b_m == 0 and t.entry_time.minute < 30) or (b_m == 30 and t.entry_time.minute >= 30))
            ]
            if t_matching:
                t_wins = sum(1 for t in t_matching if t.is_win)
                t_r = sum(t.fixed_r_target or 0.0 for t in t_matching)
                t_sr = (t_wins / len(t_matching) * 100) if t_matching else 0.0
                t_start = time(b_h, b_m)
                t_end = time(b_h if b_m == 0 else (b_h + 1) % 24, 30 if b_m == 0 else 0)
                label_12h = f"{format_time_12h(t_start)} – {format_time_12h(t_end)}"
                time_rankings.append({
                    "interval": label_12h,
                    "trades": len(t_matching),
                    "wins": t_wins,
                    "losses": len(t_matching) - t_wins,
                    "win_rate": round(t_sr, 1),
                    "total_r": round(t_r, 2),
                })

        time_rankings.sort(key=lambda x: (x["total_r"], x["win_rate"]), reverse=True)
        best_time_windows = time_rankings[:3]
        worst_time_windows = [t for t in time_rankings if t["total_r"] < 0 or t["win_rate"] == 0]
        worst_time_window = worst_time_windows[-1] if worst_time_windows else None

        # 4. Session Rankings
        sessions = db.query(Session).all()
        session_rankings = []
        for s in sessions:
            s_trades = [t for t in trades_list if t.session_id == s.id]
            if s_trades:
                s_wins = sum(1 for t in s_trades if t.is_win)
                s_r = sum(t.fixed_r_target or 0.0 for t in s_trades)
                s_sr = (s_wins / len(s_trades) * 100) if s_trades else 0.0
                share = (s_r / total_r * 100) if total_r > 0 else 0.0
                session_rankings.append({
                    "name": s.name,
                    "trades": len(s_trades),
                    "wins": s_wins,
                    "win_rate": round(s_sr, 1),
                    "total_r": round(s_r, 2),
                    "share": round(share, 1),
                })
        session_rankings.sort(key=lambda x: (x["total_r"], x["win_rate"]), reverse=True)

        # 5. Day of Week Rankings
        day_rankings = []
        for w_idx in range(7):
            d_trades = [t for t in trades_list if t.entry_date and t.entry_date.weekday() == w_idx]
            if d_trades:
                d_wins = sum(1 for t in d_trades if t.is_win)
                d_r = sum(t.fixed_r_target or 0.0 for t in d_trades)
                d_sr = (d_wins / len(d_trades) * 100) if d_trades else 0.0
                day_rankings.append({
                    "name": DAYS_MAP[w_idx],
                    "trades": len(d_trades),
                    "wins": d_wins,
                    "win_rate": round(d_sr, 1),
                    "total_r": round(d_r, 2),
                })
        day_rankings.sort(key=lambda x: (x["total_r"], x["win_rate"]), reverse=True)

        # 6. Cumulative R data series
        cum_labels = []
        cum_values = []
        running_c = 0.0
        for idx, t in enumerate(trades_list):
            running_c += (t.fixed_r_target or 0.0)
            d_str = t.entry_date.strftime("%b %d") if t.entry_date else f"#{idx+1}"
            cum_labels.append(d_str)
            cum_values.append(round(running_c, 2))

        # 7. Recent 5 trades
        recent_trades = list(reversed(trades_list))[:5]

        # 8. Automated Smart Edge Insights
        smart_insights = []
        if coin_rankings:
            top_c = coin_rankings[0]
            smart_insights.append({
                "type": "gold",
                "title": f"Top Profit Asset: {top_c['name']}",
                "desc": f"Generated +{top_c['total_r']}R with a {top_c['win_rate']}% strike rate across {top_c['trades']} trades."
            })
        if strat_rankings:
            top_s = strat_rankings[0]
            smart_insights.append({
                "type": "blue",
                "title": f"A+ Setup: {top_s['name']}",
                "desc": f"Your highest EV model delivering +{top_s['total_r']}R with {top_s['win_rate']}% win rate."
            })
        if session_rankings:
            top_sess = session_rankings[0]
            smart_insights.append({
                "type": "purple",
                "title": f"Prime Session: {top_sess['name']}",
                "desc": f"Produces {top_sess['share']}% of your portfolio return ({top_sess['total_r']}R, {top_sess['win_rate']}% win rate)."
            })
        if best_time_windows:
            top_w = best_time_windows[0]
            smart_insights.append({
                "type": "emerald",
                "title": f"Golden Window (PHT): {top_w['interval']}",
                "desc": f"100% execution conviction producing +{top_w['total_r']}R ({top_w['trades']} wins)."
            })

    stats = {
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 1),
        "total_r": round(total_r, 2),
        "avg_r": round(avg_r, 2),
        "avg_winner": round(avg_winner, 2),
        "avg_loser": round(avg_loser, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "win_streak": max_win_streak,
        "loss_streak": max_loss_streak,
        "peak_r": round(peak_r, 2),
        "max_drawdown": round(max_dd, 2),
    }

    outcome_stats = compute_execution_outcomes(trades_list)
    psychology_stats = compute_psychology_stats(trades_list)
    exec_status_stats = compute_execution_status_stats(trades_list)
    fear_greed_matrix = compute_fear_greed_matrix(trades_list)
    alerts = check_alerts()

    return templates.TemplateResponse(
        request,
        "dashboard/index.html",
        {
            "stats": stats,
            "active_year": active_year_str if active_year_str else "All-Time",
            "coin_rankings": coin_rankings,
            "strat_rankings": strat_rankings,
            "best_time_windows": best_time_windows,
            "worst_time_window": worst_time_window,
            "session_rankings": session_rankings,
            "day_rankings": day_rankings,
            "cum_labels": cum_labels,
            "cum_values": cum_values,
            "recent_trades": recent_trades,
            "smart_insights": smart_insights,
            "alerts": alerts,
            "outcome_stats": outcome_stats,
            "psychology_stats": psychology_stats,
            "exec_status_stats": exec_status_stats,
            "fear_greed_matrix": fear_greed_matrix,
        },
    )
