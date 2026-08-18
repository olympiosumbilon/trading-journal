from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
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

DAYS_MAP = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI", 5: "SAT", 6: "SUN"}


def calc_all_time_kpi(trades):
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

    commission_buffer = 0.3
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
def summary(request: Request, year: str = ""):
    with SessionLocal() as db:
        # Load all trades sorted chronologically
        query = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
            )
            .order_by(Trade.entry_date.asc(), Trade.entry_time.asc(), Trade.id.asc())
        )
        
        all_raw_trades = query.all()
        
        # Available years for dropdown
        db_years = (
            db.query(Trade.year)
            .filter(Trade.year.isnot(None))
            .distinct()
            .order_by(Trade.year.asc())
            .all()
        )
        years_list = sorted(list(set([y[0] for y in db_years] + list(range(2022, 2035)))))

        cookie_year = request.cookies.get("active_year", "")
        selected_year_str = year.strip() if year else (cookie_year.strip() if cookie_year else "")
        if selected_year_str and selected_year_str != "all":
            try:
                filter_year = int(selected_year_str)
                trades = [t for t in all_raw_trades if t.year == filter_year]
            except ValueError:
                filter_year = None
                trades = all_raw_trades
        else:
            filter_year = None
            trades = all_raw_trades

        strategies = db.query(Strategy).order_by(Strategy.name).all()
        # Smart Strategy Scoping: Only include strategies traded in current view or active
        if filter_year:
            strategies = [st for st in strategies if any(t.strategy_id == st.id for t in trades) or bool(getattr(st, "is_active", True))]
        else:
            strategies = [st for st in strategies if any(t.strategy_id == st.id for t in all_raw_trades) or bool(getattr(st, "is_active", True))]

        instruments = db.query(Instrument).order_by(Instrument.name).all()
        sessions = db.query(Session).order_by(Session.name).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        # 1. KPI Summary Card
        kpi_summary = calc_all_time_kpi(trades)

        # 2. Cumulative R Chart Series
        cum_labels = ["Start"] if trades else []
        cum_values = [0.0] if trades else []
        running_cum_r = 0.0
        for idx, t in enumerate(trades):
            running_cum_r += (t.fixed_r_target or 0.0)
            d_str = t.entry_date.strftime("%b %d") if t.entry_date else f"#{idx+1}"
            cum_labels.append(d_str)
            cum_values.append(round(running_cum_r, 2))

        # 3. Multi-Year Strategy Performance Matrix
        db_years = (
            db.query(Trade.year)
            .filter(Trade.year.isnot(None))
            .distinct()
            .order_by(Trade.year.asc())
            .all()
        )
        years_list = sorted(list(set([y[0] for y in db_years] + [2022, 2023, 2024])))

        years_matrix = []
        for y in years_list:
            y_trades = [t for t in all_raw_trades if t.year == y]
            y_wins = sum(1 for t in y_trades if t.is_win)
            y_total_r = sum(t.fixed_r_target or 0.0 for t in y_trades)
            y_sr = (y_wins / len(y_trades) * 100) if y_trades else 0.0

            strat_cols = {}
            for st in strategies:
                st_trades = [t for t in y_trades if t.strategy_id == st.id]
                st_wins = sum(1 for t in st_trades if t.is_win)
                st_r = sum(t.fixed_r_target or 0.0 for t in st_trades)
                st_sr = (st_wins / len(st_trades) * 100) if st_trades else 0.0
                strat_cols[st.id] = {
                    "trades": len(st_trades),
                    "sr": round(st_sr, 2),
                    "r": round(st_r, 2),
                    "trades_list": [serialize_trade_preview(t) for t in st_trades],
                    "filter_url": f"/trades/?strategy={st.id}&year={y}",
                }

            years_matrix.append({
                "year": y,
                "trades": len(y_trades),
                "sr": round(y_sr, 2),
                "r": round(y_total_r, 2),
                "strat_cols": strat_cols,
                "trades_list": [serialize_trade_preview(t) for t in y_trades],
                "filter_url": f"/trades/?year={y}",
            })

        # Matrix Totals Row
        total_strat_cols = {}
        for st in strategies:
            st_trades = [t for t in trades if t.strategy_id == st.id]
            st_wins = sum(1 for t in st_trades if t.is_win)
            st_r = sum(t.fixed_r_target or 0.0 for t in st_trades)
            st_sr = (st_wins / len(st_trades) * 100) if st_trades else 0.0
            total_strat_cols[st.id] = {
                "trades": len(st_trades),
                "sr": round(st_sr, 2),
                "r": round(st_r, 2),
                "trades_list": [serialize_trade_preview(t) for t in st_trades],
                "filter_url": f"/trades/?strategy={st.id}" + (f"&year={filter_year}" if filter_year else ""),
            }

        matrix_total_row = {
            "trades": len(trades),
            "sr": kpi_summary["strike_rate"],
            "r": kpi_summary["total_r"],
            "strat_cols": total_strat_cols,
            "trades_list": [serialize_trade_preview(t) for t in trades],
            "filter_url": f"/trades/" + (f"?year={filter_year}" if filter_year else ""),
        }

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
                "filter_url": f"/trades/?instrument={inst.id}",
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
                "filter_url": f"/trades/?probability={p.id}",
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
                "filter_url": f"/trades/?phase={ph.id}",
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
                "filter_url": f"/trades/?day_idx={w_idx}",
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
                "filter_url": f"/trades/?session={s.id}",
            })

        # 9. Time of Day (30-min intervals)
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

        outcome_stats = compute_execution_outcomes(trades)
        psychology_stats = compute_psychology_stats(trades)
        exec_status_stats = compute_execution_status_stats(trades)

    return templates.TemplateResponse(
        request,
        "summary/index.html",
        {
            "summary": kpi_summary,
            "cum_labels": cum_labels,
            "cum_values": cum_values,
            "strategies": strategies,
            "years_matrix": years_matrix,
            "matrix_total_row": matrix_total_row,
            "inst_breakdown": inst_breakdown,
            "prob_breakdown": prob_breakdown,
            "phase_breakdown": phase_breakdown,
            "days_breakdown": days_breakdown,
            "session_breakdown": session_breakdown,
            "time_breakdown": time_breakdown,
            "years": years_list,
            "selected_year": filter_year,
            "outcome_stats": outcome_stats,
            "psychology_stats": psychology_stats,
            "exec_status_stats": exec_status_stats,
        },
    )
