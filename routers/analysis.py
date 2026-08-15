from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from sqlalchemy import func
from datetime import datetime
from database import SessionLocal
from models import Trade, Instrument, Session, Strategy, ProbabilityLevel, MTFPhase
from services.calculation_service import (
    compute_execution_outcomes,
    compute_psychology_stats,
    compute_execution_status_stats,
    serialize_trade_preview,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")

MONTH_NAMES = [
    "", "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
]

DAYS_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}


def calc_kpi_stats(trades):
    total_trades = len(trades)
    wins = sum(1 for t in trades if t.is_win)
    losses = sum(1 for t in trades if t.is_loss)
    strike_rate = (wins / total_trades * 100) if total_trades else 0.0
    total_r = sum(t.fixed_r_target or 0.0 for t in trades)

    win_rs = [t.fixed_r_target for t in trades if t.is_win and t.fixed_r_target is not None]
    loss_rs = [t.fixed_r_target for t in trades if t.is_loss and t.fixed_r_target is not None]
    avg_winner = (sum(win_rs) / len(win_rs)) if win_rs else 0.0
    avg_loser = (sum(loss_rs) / len(loss_rs)) if loss_rs else 0.0

    total_win_r = sum(win_rs)
    total_loss_r = abs(sum(loss_rs))
    profit_factor = (total_win_r / total_loss_r) if total_loss_r > 0 else (total_win_r if total_win_r > 0 else 0.0)

    win_prob = wins / total_trades if total_trades else 0.0
    loss_prob = losses / total_trades if total_trades else 0.0
    expectancy = (win_prob * avg_winner) + (loss_prob * avg_loser)

    max_win_streak = 0
    max_loss_streak = 0
    curr_win = 0
    curr_loss = 0
    peak_r = 0.0
    max_dd = 0.0
    running_r = 0.0

    for t in trades:
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

    commission_buffer = 0.0
    net_r = total_r - (total_trades * commission_buffer)

    return {
        "total_r": round(total_r, 2),
        "net_r": round(net_r, 2),
        "strike_rate": round(strike_rate, 2),
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "avg_winner": round(avg_winner, 2),
        "avg_loser": round(avg_loser, 2),
        "win_streak": max_win_streak,
        "loss_streak": max_loss_streak,
        "drawdown": round(max_dd, 2),
        "profit_factor": round(profit_factor, 2),
        "expectancy": round(expectancy, 2),
        "commission_buffer": commission_buffer,
    }


@router.get("/")
def analysis(request: Request, year: str = ""):
    with SessionLocal() as db:
        # Available years from database
        db_years = (
            db.query(Trade.year)
            .filter(Trade.year.isnot(None))
            .distinct()
            .order_by(Trade.year.asc())
            .all()
        )
        years_list = [y[0] for y in db_years if y[0]]
        found_years = sorted(list(set([y[0] for y in db_years if y[0]] + list(range(2022, 2035)))))
        if not years_list:
            years_list = [datetime.now().year]

        # Determine selected year
        cookie_year = request.cookies.get("active_year", "")
        if year:
            try:
                selected_year = int(year)
            except ValueError:
                selected_year = years_list[-1]
        elif cookie_year and cookie_year != "all":
            try:
                selected_year = int(cookie_year)
            except ValueError:
                selected_year = years_list[-1]
        else:
            selected_year = years_list[-1]

        # Lookups
        sessions = db.query(Session).order_by(Session.name).all()
        instruments = db.query(Instrument).order_by(Instrument.name).all()
        strategies = db.query(Strategy).order_by(Strategy.name).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        # Trades for selected year
        trades = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
            )
            .filter(Trade.year == selected_year)
            .order_by(Trade.entry_date.asc(), Trade.entry_time.asc(), Trade.id.asc())
            .all()
        )

        # 1. Summary KPI Card
        kpi_summary = calc_kpi_stats(trades)

        # 2. Monthly Performance Matrix
        monthly_matrix = []
        for m in range(1, 13):
            m_trades = [t for t in trades if t.month_number == m]
            m_wins = sum(1 for t in m_trades if t.is_win)
            m_total_r = sum(t.fixed_r_target or 0.0 for t in m_trades)
            m_sr = (m_wins / len(m_trades) * 100) if m_trades else 0.0

            strat_cols = {}
            for st in strategies:
                st_trades = [t for t in m_trades if t.strategy_id == st.id]
                st_wins = sum(1 for t in st_trades if t.is_win)
                st_r = sum(t.fixed_r_target or 0.0 for t in st_trades)
                st_sr = (st_wins / len(st_trades) * 100) if st_trades else 0.0
                strat_cols[st.id] = {
                    "trades": len(st_trades),
                    "sr": round(st_sr, 2),
                    "r": round(st_r, 2),
                    "trades_list": [serialize_trade_preview(t) for t in st_trades],
                    "filter_url": f"/trades/?month={m}&strategy={st.id}&year={selected_year}",
                }

            monthly_matrix.append({
                "month_num": m,
                "month_name": MONTH_NAMES[m],
                "trades": len(m_trades),
                "sr": round(m_sr, 2),
                "r": round(m_total_r, 2),
                "strat_cols": strat_cols,
                "trades_list": [serialize_trade_preview(t) for t in m_trades],
                "filter_url": f"/trades/?month={m}&year={selected_year}",
            })

        # 3. Quarterly Performance Matrix
        quarterly_matrix = []
        for q in range(1, 5):
            q_months = range((q - 1) * 3 + 1, q * 3 + 1)
            q_trades = [t for t in trades if t.month_number in q_months]
            q_wins = sum(1 for t in q_trades if t.is_win)
            q_total_r = sum(t.fixed_r_target or 0.0 for t in q_trades)
            q_sr = (q_wins / len(q_trades) * 100) if q_trades else 0.0

            strat_cols = {}
            for st in strategies:
                st_trades = [t for t in q_trades if t.strategy_id == st.id]
                st_wins = sum(1 for t in st_trades if t.is_win)
                st_r = sum(t.fixed_r_target or 0.0 for t in st_trades)
                st_sr = (st_wins / len(st_trades) * 100) if st_trades else 0.0
                strat_cols[st.id] = {
                    "trades": len(st_trades),
                    "sr": round(st_sr, 2),
                    "r": round(st_r, 2),
                    "trades_list": [serialize_trade_preview(t) for t in st_trades],
                    "filter_url": f"/trades/?strategy={st.id}&year={selected_year}",
                }

            quarterly_matrix.append({
                "quarter_num": q,
                "quarter_name": f"Q{q}",
                "trades": len(q_trades),
                "sr": round(q_sr, 2),
                "r": round(q_total_r, 2),
                "strat_cols": strat_cols,
                "trades_list": [serialize_trade_preview(t) for t in q_trades],
                "filter_url": f"/trades/?year={selected_year}",
            })

        # 4. Breakdown: Instruments
        inst_breakdown = []
        for inst in instruments:
            i_trades = [t for t in trades if t.instrument_id == inst.id]
            i_wins = sum(1 for t in i_trades if t.is_win)
            i_r = sum(t.fixed_r_target or 0.0 for t in i_trades)
            i_sr = (i_wins / len(i_trades) * 100) if i_trades else 0.0
            inst_breakdown.append({
                "id": inst.id,
                "name": inst.name,
                "trades": len(i_trades),
                "sr": round(i_sr, 2),
                "r": round(i_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in i_trades],
                "filter_url": f"/trades/?instrument={inst.id}&year={selected_year}",
            })

        # 5. Breakdown: Probabilities
        prob_breakdown = []
        for p in probabilities:
            p_trades = [t for t in trades if t.probability_level_id == p.id]
            p_wins = sum(1 for t in p_trades if t.is_win)
            p_r = sum(t.fixed_r_target or 0.0 for t in p_trades)
            p_sr = (p_wins / len(p_trades) * 100) if p_trades else 0.0
            prob_breakdown.append({
                "id": p.id,
                "name": p.name,
                "trades": len(p_trades),
                "sr": round(p_sr, 2),
                "r": round(p_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in p_trades],
                "filter_url": f"/trades/?probability={p.id}&year={selected_year}",
            })

        # 6. Breakdown: MTF Phases
        phase_breakdown = []
        for ph in phases:
            ph_trades = [t for t in trades if t.mtf_phase_id == ph.id]
            ph_wins = sum(1 for t in ph_trades if t.is_win)
            ph_r = sum(t.fixed_r_target or 0.0 for t in ph_trades)
            ph_sr = (ph_wins / len(ph_trades) * 100) if ph_trades else 0.0
            phase_breakdown.append({
                "id": ph.id,
                "name": ph.name,
                "trades": len(ph_trades),
                "sr": round(ph_sr, 2),
                "r": round(ph_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in ph_trades],
                "filter_url": f"/trades/?phase={ph.id}&year={selected_year}",
            })

        # 7. Breakdown: Days of Week (MON - SUN)
        days_breakdown = []
        for w_idx in range(7):
            d_name = DAYS_MAP[w_idx]
            d_trades = [t for t in trades if t.entry_date and t.entry_date.weekday() == w_idx]
            d_wins = sum(1 for t in d_trades if t.is_win)
            d_r = sum(t.fixed_r_target or 0.0 for t in d_trades)
            d_sr = (d_wins / len(d_trades) * 100) if d_trades else 0.0
            days_breakdown.append({
                "name": d_name,
                "trades": len(d_trades),
                "sr": round(d_sr, 2),
                "r": round(d_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in d_trades],
                "filter_url": f"/trades/?day_idx={w_idx}&year={selected_year}",
            })

        # 8. Breakdown: Sessions
        session_breakdown = []
        for s in sessions:
            s_trades = [t for t in trades if t.session_id == s.id]
            s_wins = sum(1 for t in s_trades if t.is_win)
            s_r = sum(t.fixed_r_target or 0.0 for t in s_trades)
            s_sr = (s_wins / len(s_trades) * 100) if s_trades else 0.0
            session_breakdown.append({
                "id": s.id,
                "name": s.name,
                "trades": len(s_trades),
                "sr": round(s_sr, 2),
                "r": round(s_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in s_trades],
                "filter_url": f"/trades/?session={s.id}&year={selected_year}",
            })

        # 9. Monthly by Session breakdown (cards per session)
        sessions_monthly_cards = []
        for s in sessions:
            s_months = []
            s_all_trades = [t for t in trades if t.session_id == s.id]
            for m in range(1, 13):
                sm_trades = [t for t in s_all_trades if t.month_number == m]
                sm_wins = sum(1 for t in sm_trades if t.is_win)
                sm_r = sum(t.fixed_r_target or 0.0 for t in sm_trades)
                sm_sr = (sm_wins / len(sm_trades) * 100) if sm_trades else 0.0
                s_months.append({
                    "month": MONTH_NAMES[m],
                    "trades": len(sm_trades),
                    "sr": round(sm_sr, 2),
                    "r": round(sm_r, 2),
                    "trades_list": [serialize_trade_preview(t) for t in sm_trades],
                    "filter_url": f"/trades/?session={s.id}&month={m}&year={selected_year}",
                })
            s_total_wins = sum(1 for t in s_all_trades if t.is_win)
            s_total_r = sum(t.fixed_r_target or 0.0 for t in s_all_trades)
            s_total_sr = (s_total_wins / len(s_all_trades) * 100) if s_all_trades else 0.0
            sessions_monthly_cards.append({
                "session_name": s.name,
                "months": s_months,
                "total_trades": len(s_all_trades),
                "total_sr": round(s_total_sr, 2),
                "total_r": round(s_total_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in s_all_trades],
                "filter_url": f"/trades/?session={s.id}&year={selected_year}",
            })

        # 10. Time of Day (30-min intervals)
        time_buckets = []
        for h in range(24):
            h_next = (h + 1) % 24
            time_buckets.append((f"{h:02d}:00-{h:02d}:30", h, 0))
            time_buckets.append((f"{h:02d}:30-{h_next:02d}:00", h, 30))

        time_breakdown = []
        for b_name, b_h, b_m in time_buckets:
            t_matching = []
            for t in trades:
                if t.entry_time:
                    if t.entry_time.hour == b_h:
                        if b_m == 0 and t.entry_time.minute < 30:
                            t_matching.append(t)
                        elif b_m == 30 and t.entry_time.minute >= 30:
                            t_matching.append(t)
            t_wins = sum(1 for t in t_matching if t.is_win)
            t_r = sum(t.fixed_r_target or 0.0 for t in t_matching)
            t_sr = (t_wins / len(t_matching) * 100) if t_matching else 0.0
            time_breakdown.append({
                "interval": b_name,
                "trades": len(t_matching),
                "sr": round(t_sr, 2),
                "r": round(t_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in t_matching],
            })

        # 11. Chart.js Structured Payload
        chart_data = {
            "monthly": {
                "labels": [m["month_name"] for m in monthly_matrix],
                "r_data": [m["r"] for m in monthly_matrix],
                "sr_data": [m["sr"] for m in monthly_matrix],
            },
            "quarterly": {
                "labels": [q["quarter_name"] for q in quarterly_matrix],
                "r_data": [q["r"] for q in quarterly_matrix],
                "sr_data": [q["sr"] for q in quarterly_matrix],
            },
            "phases": {
                "labels": [p["name"] for p in phase_breakdown],
                "r_data": [p["r"] for p in phase_breakdown],
                "sr_data": [p["sr"] for p in phase_breakdown],
            },
            "sessions": {
                "labels": [s["name"] for s in session_breakdown],
                "r_data": [s["r"] for s in session_breakdown],
                "sr_data": [s["sr"] for s in session_breakdown],
            },
            "strategies": {
                "labels": [st.name for st in strategies],
                "r_data": [
                    round(sum(t.fixed_r_target or 0.0 for t in trades if t.strategy_id == st.id), 2)
                    for st in strategies
                ],
                "sr_data": [
                    round(
                        (sum(1 for t in trades if t.strategy_id == st.id and t.is_win) /
                         max(1, len([t for t in trades if t.strategy_id == st.id])) * 100)
                        if any(t.strategy_id == st.id for t in trades) else 0.0,
                        2
                    )
                    for st in strategies
                ],
            },
            "instruments_pie": {
                "labels": [i["name"] for i in inst_breakdown if i["r"] > 0] or ([i["name"] for i in inst_breakdown if i["trades"] > 0] or ["No Data"]),
                "data": [i["r"] for i in inst_breakdown if i["r"] > 0] or ([i["trades"] for i in inst_breakdown if i["trades"] > 0] or [1]),
                "colors": ["#a7f3d0", "#60a5fa", "#f59e0b", "#c084fc", "#f43f5e", "#38bdf8"],
            },
            "probability_pie": {
                "labels": [p["name"] for p in prob_breakdown if p["r"] > 0] or ([p["name"] for p in prob_breakdown if p["trades"] > 0] or ["No Data"]),
                "data": [p["r"] for p in prob_breakdown if p["r"] > 0] or ([p["trades"] for p in prob_breakdown if p["trades"] > 0] or [1]),
                "colors": ["#10b981", "#f59e0b", "#ef4444", "#60a5fa"],
            },
            "days": {
                "labels": [d["name"] for d in days_breakdown],
                "r_data": [d["r"] for d in days_breakdown],
                "sr_data": [d["sr"] for d in days_breakdown],
            },
        }

        outcome_stats = compute_execution_outcomes(trades)
        psychology_stats = compute_psychology_stats(trades)
        exec_status_stats = compute_execution_status_stats(trades)

    return templates.TemplateResponse(
        request,
        "analysis/index.html",
        {
            "years": found_years,
            "selected_year": selected_year,
            "strategies": strategies,
            "instruments": instruments,
            "sessions": sessions,
            "probabilities": probabilities,
            "phases": phases,
            "summary": kpi_summary,
            "monthly_matrix": monthly_matrix,
            "quarterly_matrix": quarterly_matrix,
            "inst_breakdown": inst_breakdown,
            "prob_breakdown": prob_breakdown,
            "phase_breakdown": phase_breakdown,
            "days_breakdown": days_breakdown,
            "session_breakdown": session_breakdown,
            "sessions_monthly_cards": sessions_monthly_cards,
            "time_breakdown": time_breakdown,
            "chart_data": chart_data,
            "outcome_stats": outcome_stats,
            "psychology_stats": psychology_stats,
            "exec_status_stats": exec_status_stats,
        },
    )
