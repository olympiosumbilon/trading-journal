from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, asc, func, extract, case
from sqlalchemy.orm import selectinload
from database import SessionLocal
from models import (
    Trade, Session, Instrument, Strategy, ProbabilityLevel, MTFPhase, TradeScreenshot,
)
from services.calculation_service import (
    compute_max_r, compute_fixed_r_target, compute_portfolio_stats,
)
import shutil
import os
import re
from pathlib import Path
from utils.template_helpers import format_time_12h, format_duration
from datetime import date, datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["time_12h"] = format_time_12h
templates.env.filters["duration"] = format_duration


MEDIA_DIR = Path("media/screenshots")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def sync_trade_screenshots(db, trade: Trade, raw_urls: list[str], raw_captions: list[str] = None):
    clean_items = []
    raw_captions = raw_captions or []
    for idx, u in enumerate(raw_urls):
        if not u:
            continue
        p_clean = str(u).strip()
        c_clean = str(raw_captions[idx]).strip() if idx < len(raw_captions) and raw_captions[idx] else None
        if p_clean:
            clean_items.append((p_clean, c_clean))

    db.query(TradeScreenshot).filter(TradeScreenshot.trade_id == trade.id).delete()
    for idx, (u, cap) in enumerate(clean_items):
        db.add(TradeScreenshot(trade_id=trade.id, url=u, caption=cap, order_index=idx))

    trade.screenshot_1 = clean_items[0][0] if len(clean_items) > 0 else None
    trade.screenshot_2 = clean_items[1][0] if len(clean_items) > 1 else None
    trade.screenshot_3 = clean_items[2][0] if len(clean_items) > 2 else None



def auto_detect_session_id(db, time_str: str):
    if not time_str or not str(time_str).strip():
        return None
    try:
        parts = str(time_str).strip().split(":")
        h = int(parts[0])
        m = int(parts[1][:2])
        mins = h * 60 + m
    except Exception:
        return None

    # Philippine Time (UTC+8) Session Schedule:
    if 480 <= mins < 840:       # 08:00 AM - 01:59 PM (480-839 mins)
        target = "ASIA"
    elif 840 <= mins < 1140:    # 02:00 PM - 06:59 PM (840-1139 mins) -> London Open (PHT)
        target = "LDN"
    elif 1140 <= mins < 1200:   # 07:00 PM - 07:59 PM (1140-1199 mins)
        target = "LDN LULL"
    elif 1200 <= mins <= 1439:  # 08:00 PM - 11:59 PM (1200-1439 mins) -> New York Open (PHT)
        target = "NY"
    else:                       # 12:00 AM - 07:59 AM (0-479 mins)
        target = "NY LULL"

    sess = db.query(Session).filter(Session.name.ilike(target)).first()
    return sess.id if sess else None



def resolve_screenshot(val: str) -> dict:
    if not val or not str(val).strip():
        return None
    val = str(val).strip()
    
    # Match TradingView share links: e.g. https://www.tradingview.com/x/GAxHDxmH/ or /x/GAxHDxmH
    m = re.search(r'tradingview\.com/x/([a-zA-Z0-9]+)', val)
    if m:
        tv_id = m.group(1)
        first_letter = tv_id[0].lower()
        img_src = f"https://s3.tradingview.com/snapshots/{first_letter}/{tv_id}.png"
        link_url = f"https://www.tradingview.com/x/{tv_id}/"
        return {
            "img_src": img_src,
            "link_url": link_url,
            "raw_val": val,
            "is_tv": True,
            "tv_id": tv_id,
        }

    # Match other direct web image links
    if val.startswith("http://") or val.startswith("https://"):
        return {
            "img_src": val,
            "link_url": val,
            "raw_val": val,
            "is_tv": False,
            "tv_id": None,
        }

    # Local file path
    local_path = val.lstrip("/")
    return {
        "img_src": f"/{local_path}",
        "link_url": f"/{local_path}",
        "raw_val": val,
        "is_tv": False,
        "tv_id": None,
    }


def get_lookup_data(db):
    return {
        "sessions": db.query(Session).order_by(Session.name).all(),
        "instruments": db.query(Instrument).order_by(Instrument.name).all(),
        "strategies": db.query(Strategy).order_by(Strategy.name).all(),
        "probabilities": db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all(),
        "phases": db.query(MTFPhase).order_by(MTFPhase.name).all(),
    }


@router.get("/")
def list_trades(
    request: Request,
    year: str = "",
    month: str = "",
    session: str = "",
    instrument: str = "",
    strategy: str = "",
    probability: str = "",
    phase: str = "",
    day_idx: str = "",
    outcome: str = "",
    emotion_before: str = "",
    emotion_after: str = "",
    tag: str = "",
    page: int = 1,
    per_page: int = 10,
    sort_by: str = "date_desc",
):
    valid_per_page = [10, 25, 30, 50, 100]
    if per_page not in valid_per_page:
        per_page = 10

    cookie_year = request.cookies.get("active_year", "")
    if not year and cookie_year and cookie_year != "all":
        year = cookie_year

    with SessionLocal() as db:
        query = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
            )
        )

        if year and year != "all":
            try:
                query = query.filter(Trade.year == int(year))
            except ValueError:
                pass
        if month:
            query = query.filter(Trade.month_number == int(month))
        if session:
            query = query.filter(Trade.session_id == int(session))
        if instrument:
            query = query.filter(Trade.instrument_id == int(instrument))
        if strategy:
            query = query.filter(Trade.strategy_id == int(strategy))
        if probability:
            query = query.filter(Trade.probability_level_id == int(probability))
        if phase:
            query = query.filter(Trade.mtf_phase_id == int(phase))

        # Day of Week Filter (0=Mon .. 6=Sun)
        if day_idx is not None and day_idx != "":
            try:
                d_val = int(day_idx)
                # In PostgreSQL, isodow is 1 (Monday) to 7 (Sunday)
                query = query.filter(extract('isodow', Trade.entry_date) == (d_val + 1))
            except ValueError:
                pass

        # Outcome Type Filter
        if outcome:
            out_up = outcome.upper()
            otype_col = func.coalesce(Trade.outcome_type, 'AUTO')
            if out_up == "FULL_TP":
                query = query.filter(
                    (Trade.outcome_type == 'FULL_TP') |
                    ((otype_col == 'AUTO') & (Trade.fixed_r_target > 0))
                )
            elif out_up == "BREAK_EVEN":
                query = query.filter(
                    (Trade.outcome_type == 'BREAK_EVEN') |
                    ((otype_col == 'AUTO') & (Trade.fixed_r_target == 0))
                )
            elif out_up == "FULL_SL":
                query = query.filter(
                    (Trade.outcome_type == 'FULL_SL') |
                    ((otype_col == 'AUTO') & (Trade.fixed_r_target < 0))
                )
            else:
                query = query.filter(Trade.outcome_type == out_up)

        # Psychology / Emotion Filters
        if emotion_before:
            query = query.filter(func.upper(Trade.emotion_before) == emotion_before.upper())
        if emotion_after:
            query = query.filter(func.upper(Trade.emotion_after) == emotion_after.upper())

        # Execution Tag Filter
        if tag == "LIVE":
            query = query.filter(
                (Trade.execution_status == 'LIVE') | (Trade.execution_status.is_(None)),
                (Trade.is_sl_swept == False) | (Trade.is_sl_swept.is_(None))
            )
        elif tag == "FRONT_RUN":
            query = query.filter(Trade.execution_status == 'FRONT_RUN')
        elif tag == "MISSED":
            query = query.filter(Trade.execution_status == 'MISSED')
        elif tag == "SL_SWEPT":
            query = query.filter(Trade.is_sl_swept == True)

        # Sorting logic
        if sort_by == "date_asc":
            query = query.order_by(Trade.entry_date.asc().nullslast(), Trade.entry_time.asc().nullslast(), Trade.id.asc())
        elif sort_by == "missed_first":
            query = query.order_by(
                case((Trade.execution_status == 'MISSED', 0), else_=1),
                Trade.entry_date.desc().nullslast(),
                Trade.id.desc()
            )
        elif sort_by == "front_run_first":
            query = query.order_by(
                case((Trade.execution_status == 'FRONT_RUN', 0), else_=1),
                Trade.entry_date.desc().nullslast(),
                Trade.id.desc()
            )
        elif sort_by == "sl_swept_first":
            query = query.order_by(
                case((Trade.is_sl_swept == True, 0), else_=1),
                Trade.entry_date.desc().nullslast(),
                Trade.id.desc()
            )
        elif sort_by == "tags_first":
            query = query.order_by(
                case(
                    (Trade.execution_status == 'MISSED', 0),
                    (Trade.execution_status == 'FRONT_RUN', 1),
                    (Trade.is_sl_swept == True, 2),
                    else_=3
                ),
                Trade.entry_date.desc().nullslast(),
                Trade.id.desc()
            )
        elif sort_by == "max_r_desc":
            query = query.order_by(Trade.max_r.desc().nullslast(), Trade.id.desc())
        elif sort_by == "max_r_asc":
            query = query.order_by(Trade.max_r.asc().nullslast(), Trade.id.asc())
        elif sort_by == "fixed_r_desc":
            query = query.order_by(Trade.fixed_r_target.desc().nullslast(), Trade.id.desc())
        elif sort_by == "fixed_r_asc":
            query = query.order_by(Trade.fixed_r_target.asc().nullslast(), Trade.id.asc())
        elif sort_by == "total_r_desc":
            query = query.order_by(Trade.fixed_r_target.desc().nullslast(), Trade.id.desc())
        else:
            # Default: date_desc
            query = query.order_by(Trade.entry_date.desc().nullslast(), Trade.entry_time.desc().nullslast(), Trade.id.desc())

        total_count = query.count()
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * per_page

        trades = query.offset(offset).limit(per_page).all()
        lookups = get_lookup_data(db)

    # Build base query string for pagination links (without page param)
    filter_params = {k: str(v) for k, v in {
        "year": year,
        "month": month,
        "session": session,
        "instrument": instrument,
        "strategy": strategy,
        "probability": probability,
        "phase": phase,
        "day_idx": day_idx,
        "outcome": outcome,
        "emotion_before": emotion_before,
        "emotion_after": emotion_after,
        "tag": tag,
        "per_page": per_page if per_page != 10 else "",
        "sort_by": sort_by if sort_by != "date_desc" else "",
    }.items() if v}

    # Construct descriptive active filter labels
    active_filters_list = []
    if outcome:
        out_names = {
            "FULL_TP": "🎯 Hit Full TP",
            "RUNNER": "🚀 Runner / Exceeded TP",
            "BREAK_EVEN": "⚖️ Break Even",
            "TRAILING_STOP": "🛡️ Trailing Stop",
            "CUT_LOSS": "✂️ Early Cut Loss",
            "FULL_SL": "❌ Full Stop Loss",
        }
        active_filters_list.append(out_names.get(outcome.upper(), f"Outcome: {outcome}"))
    if tag:
        tag_names = {"LIVE": "🟢 Live Trades", "FRONT_RUN": "🟡 Front-Run", "MISSED": "⚪ Missed", "SL_SWEPT": "🪤 SL Swept"}
        active_filters_list.append(tag_names.get(tag.upper(), f"Tag: {tag}"))
    if day_idx is not None and day_idx != "":
        d_map = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        try:
            active_filters_list.append(f"📅 {d_map[int(day_idx)]}")
        except Exception:
            pass
    if emotion_before:
        active_filters_list.append(f"🧘 Before: {emotion_before.title()}")
    if emotion_after:
        active_filters_list.append(f"🏁 After: {emotion_after.title()}")

    return templates.TemplateResponse(
        request,
        "trades/list.html",
        {
            "trades": trades,
            **lookups,
            "active_filter_label": " • ".join(active_filters_list) if active_filters_list else "",
            "filters": {
                "year": year,
                "month": month,
                "session": session,
                "instrument": instrument,
                "strategy": strategy,
                "probability": probability,
                "phase": phase,
                "day_idx": day_idx,
                "outcome": outcome,
                "emotion_before": emotion_before,
                "emotion_after": emotion_after,
                "tag": tag,
            },
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "per_page": per_page,
            "sort_by": sort_by,
            "filter_params": filter_params,
        },
    )


@router.get("/new")
def new_trade(request: Request):
    with SessionLocal() as db:
        lookups = get_lookup_data(db)
    
    prefill = dict(request.query_params)
    prefill_screenshots = []
    # Collect screenshot_1, screenshot_2, screenshot_3, ... from prefill in natural order
    shot_keys = sorted([k for k in prefill.keys() if k.startswith("screenshot_")], key=lambda x: int(x.split("_")[1]) if x.split("_")[1].isdigit() else 99)
    for k in shot_keys:
        num = k.split("_")[1]
        cap = prefill.get(f"caption_{num}", "").strip()
        if prefill[k] and prefill[k].strip():
            prefill_screenshots.append({
                "url": prefill[k].strip(),
                "caption": cap
            })

    today_str = date.today().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%H:%M")

    return templates.TemplateResponse(
        request, "trades/form.html", {
            "trade": None,
            "prefill": prefill,
            "prefill_screenshots": prefill_screenshots,
            "today_date": today_str,
            "now_time": now_str,
            **lookups
        }
    )


@router.post("/")
def create_trade(
    request: Request,
    entry_date: str = Form(""),
    entry_time: str = Form(""),
    exit_date: str = Form(""),
    exit_time: str = Form(""),
    session_id: str = Form(""),
    instrument_id: str = Form(""),
    new_instrument: str = Form(""),
    strategy_id: str = Form(""),
    probability_level_id: str = Form(""),
    mtf_phase_id: str = Form(""),
    entry_news: str = Form(""),
    management_news: str = Form(""),
    entry_candle_size: str = Form(""),
    adverse_wick_price: str = Form(""),
    mae_sl_buffer: str = Form(""),
    mfe: str = Form(""),
    comments: str = Form(""),
    execution_status: str = Form("LIVE"),
    is_sl_swept: str = Form(""),
    outcome_type: str = Form("AUTO"),
    realized_r: str = Form(""),
    emotion_before: str = Form(""),
    emotion_after: str = Form(""),
    screenshot_1: str = Form(""),
    screenshot_2: str = Form(""),
    screenshot_3: str = Form(""),
    screenshot_bulk: str = Form(""),
    screenshots: list[str] = Form([]),
    captions: list[str] = Form([]),
    from_watchlist_id: str = Form(""),
):
    with SessionLocal() as db:
        # Resolve instrument: by ID or find/create by name
        target_inst_name = new_instrument.strip().upper() if new_instrument else ""
        if instrument_id and instrument_id.isdigit():
            inst = db.query(Instrument).get(int(instrument_id))
        elif target_inst_name:
            inst = db.query(Instrument).filter(Instrument.name.ilike(target_inst_name)).first()
            if not inst:
                slug = re.sub(r'[^a-zA-Z0-9]', '', target_inst_name).lower()
                inst = Instrument(name=target_inst_name, slug=slug, sl_buffer=0.0, fixed_r_target=3.30)
                db.add(inst)
                db.flush()
        else:
            inst = None

        final_instrument_id = inst.id if inst else None

        # Auto-detect session if not manually selected
        final_session_id = int(session_id) if session_id else auto_detect_session_id(db, entry_time)

        # Parse date and time
        from datetime import datetime, timedelta
        parsed_date = None
        if entry_date and str(entry_date).strip():
            try:
                parsed_date = datetime.strptime(str(entry_date).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        parsed_time = None
        if entry_time and str(entry_time).strip():
            for t_fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    parsed_time = datetime.strptime(str(entry_time).strip(), t_fmt).time()
                    break
                except ValueError:
                    pass

        parsed_exit_date = None
        if exit_date and str(exit_date).strip():
            try:
                parsed_exit_date = datetime.strptime(str(exit_date).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        parsed_exit_time = None
        if exit_time and str(exit_time).strip():
            for t_fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    parsed_exit_time = datetime.strptime(str(exit_time).strip(), t_fmt).time()
                    break
                except ValueError:
                    pass

        # Compute Holding Duration in Minutes
        holding_time_minutes = None
        if parsed_time and parsed_exit_time:
            e_date = parsed_date or datetime.today().date()
            x_date = parsed_exit_date or e_date
            e_dt = datetime.combine(e_date, parsed_time)
            x_dt = datetime.combine(x_date, parsed_exit_time)
            if x_dt < e_dt and not parsed_exit_date:
                x_dt += timedelta(days=1)
            diff = (x_dt - e_dt).total_seconds()
            if diff >= 0:
                holding_time_minutes = int(diff // 60)

        parsed_realized_r = None
        if realized_r and str(realized_r).strip():
            try:
                parsed_realized_r = float(str(realized_r).strip())
            except ValueError:
                pass

        trade = Trade(
            entry_date=parsed_date,
            entry_time=parsed_time,
            exit_date=parsed_exit_date,
            exit_time=parsed_exit_time,
            holding_time_minutes=holding_time_minutes,
            session_id=final_session_id,
            instrument_id=final_instrument_id,
            strategy_id=int(strategy_id) if strategy_id else None,
            probability_level_id=int(probability_level_id) if probability_level_id else None,
            mtf_phase_id=int(mtf_phase_id) if mtf_phase_id else None,
            entry_news=entry_news or None,
            management_news=management_news or None,
            entry_candle_size=float(entry_candle_size) if entry_candle_size else None,
            adverse_wick_price=float(adverse_wick_price) if adverse_wick_price else None,
            mae_sl_buffer=float(mae_sl_buffer) if mae_sl_buffer else None,
            mfe=float(mfe) if mfe else None,
            comments=comments or None,
            execution_status=execution_status.strip().upper() if execution_status else "LIVE",
            is_sl_swept=bool(is_sl_swept and is_sl_swept in ("1", "true", "True", "on", True)),
            outcome_type=outcome_type or "AUTO",
            realized_r=parsed_realized_r,
            emotion_before=emotion_before.strip() if emotion_before else None,
            emotion_after=emotion_after.strip() if emotion_after else None,
        )

        if parsed_date:
            trade.day = parsed_date.day
            trade.day_of_week = parsed_date.weekday()
            trade.month_number = parsed_date.month
            trade.month_name = parsed_date.strftime("%B")
            trade.year = parsed_date.year
            trade.quarter = (parsed_date.month - 1) // 3 + 1

        # Compute derived fields
        trade.max_r = compute_max_r(
            trade.entry_candle_size,
            trade.mfe,
            trade.mae_sl_buffer,
            inst.sl_buffer if inst else None,
        )
        if parsed_realized_r is not None:
            trade.fixed_r_target = parsed_realized_r
        else:
            trade.fixed_r_target = compute_fixed_r_target(
                trade.max_r,
                inst.fixed_r_target if inst else None,
            )

        db.add(trade)
        db.commit()
        db.refresh(trade)

        # Collect and sync all screenshots
        raw_urls = list(screenshots) if screenshots else []
        if screenshot_bulk:
            raw_urls.extend(re.split(r'[\r\n,]+', screenshot_bulk))
        for s_ind in [screenshot_1, screenshot_2, screenshot_3]:
            if s_ind and s_ind.strip():
                raw_urls.append(s_ind.strip())
        sync_trade_screenshots(db, trade, raw_urls, captions)

        # Link WatchlistIdea if promoted from watchlist
        if from_watchlist_id and str(from_watchlist_id).isdigit():
            from models import WatchlistIdea
            wl_idea = db.get(WatchlistIdea, int(from_watchlist_id))
            if wl_idea:
                wl_idea.promoted_trade_id = trade.id
                wl_idea.status = "EXECUTED"

        db.commit()

        # Recalculate portfolio stats for all trades
        all_trades = db.query(Trade).order_by(Trade.id).all()
        for t in all_trades:
            _ = t.instrument_obj
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
        db.commit()

    return RedirectResponse("/trades/", status_code=303)


@router.get("/{trade_id}")
def trade_detail(request: Request, trade_id: int):
    with SessionLocal() as db:
        trade = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
                selectinload(Trade.screenshots_list),
            )
            .get(trade_id)
        )
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        # Collect all screenshots dynamically
        all_screenshots = []
        seen_urls = set()
        if trade.screenshots_list:
            for s_row in trade.screenshots_list:
                u_str = s_row.url.strip() if s_row.url else ""
                if u_str and u_str not in seen_urls:
                    seen_urls.add(u_str)
                    res = resolve_screenshot(u_str)
                    if res:
                        res["id"] = s_row.id
                        res["caption"] = s_row.caption
                        all_screenshots.append(res)

        for idx, legacy in enumerate([trade.screenshot_1, trade.screenshot_2, trade.screenshot_3], 1):
            u_str = legacy.strip() if legacy else ""
            if u_str and u_str not in seen_urls:
                seen_urls.add(u_str)
                res = resolve_screenshot(u_str)
                if res:
                    res["id"] = None
                    res["caption"] = f"Screenshot #{idx}"
                    all_screenshots.append(res)

    return templates.TemplateResponse(
        request,
        "trades/detail.html",
        {
            "trade": trade,
            "all_screenshots": all_screenshots,
        },
    )


@router.get("/{trade_id}/edit")
def edit_trade(request: Request, trade_id: int):
    with SessionLocal() as db:
        trade = (
            db.query(Trade)
            .options(
                selectinload(Trade.session_obj),
                selectinload(Trade.instrument_obj),
                selectinload(Trade.strategy_obj),
                selectinload(Trade.probability_level_obj),
                selectinload(Trade.mtf_phase_obj),
                selectinload(Trade.screenshots_list),
            )
            .get(trade_id)
        )
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        existing_screenshots = []
        if trade.screenshots_list:
            for s_row in trade.screenshots_list:
                u_str = s_row.url.strip() if s_row.url else ""
                if u_str:
                    existing_screenshots.append({
                        "url": u_str,
                        "caption": s_row.caption or ""
                    })
        if not existing_screenshots:
            for idx, legacy in enumerate([trade.screenshot_1, trade.screenshot_2, trade.screenshot_3], 1):
                u_str = legacy.strip() if legacy else ""
                if u_str:
                    existing_screenshots.append({
                        "url": u_str,
                        "caption": f"Screenshot #{idx}"
                    })

        lookups = get_lookup_data(db)

    return templates.TemplateResponse(
        request, "trades/form.html", {
            "trade": trade,
            "existing_screenshots": existing_screenshots,
            **lookups,
        }
    )


@router.post("/{trade_id}/edit")
def update_trade(
    request: Request,
    trade_id: int,
    entry_date: str = Form(""),
    entry_time: str = Form(""),
    exit_date: str = Form(""),
    exit_time: str = Form(""),
    session_id: str = Form(""),
    instrument_id: str = Form(""),
    new_instrument: str = Form(""),
    strategy_id: str = Form(""),
    probability_level_id: str = Form(""),
    mtf_phase_id: str = Form(""),
    entry_news: str = Form(""),
    management_news: str = Form(""),
    entry_candle_size: str = Form(""),
    adverse_wick_price: str = Form(""),
    mae_sl_buffer: str = Form(""),
    mfe: str = Form(""),
    comments: str = Form(""),
    execution_status: str = Form("LIVE"),
    is_sl_swept: str = Form(""),
    outcome_type: str = Form("AUTO"),
    realized_r: str = Form(""),
    emotion_before: str = Form(""),
    emotion_after: str = Form(""),
    screenshot_1: str = Form(""),
    screenshot_2: str = Form(""),
    screenshot_3: str = Form(""),
    screenshot_bulk: str = Form(""),
    screenshots: list[str] = Form([]),
    captions: list[str] = Form([]),
):
    with SessionLocal() as db:
        trade = db.query(Trade).get(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        target_inst_name = new_instrument.strip().upper() if new_instrument else ""
        if instrument_id and instrument_id.isdigit():
            inst = db.query(Instrument).get(int(instrument_id))
        elif target_inst_name:
            inst = db.query(Instrument).filter(Instrument.name.ilike(target_inst_name)).first()
            if not inst:
                slug = re.sub(r'[^a-zA-Z0-9]', '', target_inst_name).lower()
                inst = Instrument(name=target_inst_name, slug=slug, sl_buffer=0.0, fixed_r_target=3.30)
                db.add(inst)
                db.flush()
        else:
            inst = None

        final_instrument_id = inst.id if inst else None

        # Parse date and time
        from datetime import datetime, timedelta
        parsed_date = None
        if entry_date and str(entry_date).strip():
            try:
                parsed_date = datetime.strptime(str(entry_date).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        parsed_time = None
        if entry_time and str(entry_time).strip():
            for t_fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    parsed_time = datetime.strptime(str(entry_time).strip(), t_fmt).time()
                    break
                except ValueError:
                    pass

        parsed_exit_date = None
        if exit_date and str(exit_date).strip():
            try:
                parsed_exit_date = datetime.strptime(str(exit_date).strip(), "%Y-%m-%d").date()
            except Exception:
                pass

        parsed_exit_time = None
        if exit_time and str(exit_time).strip():
            for t_fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
                try:
                    parsed_exit_time = datetime.strptime(str(exit_time).strip(), t_fmt).time()
                    break
                except ValueError:
                    pass

        # Compute Holding Duration in Minutes
        holding_time_minutes = None
        if parsed_time and parsed_exit_time:
            e_date = parsed_date or datetime.today().date()
            x_date = parsed_exit_date or e_date
            e_dt = datetime.combine(e_date, parsed_time)
            x_dt = datetime.combine(x_date, parsed_exit_time)
            if x_dt < e_dt and not parsed_exit_date:
                x_dt += timedelta(days=1)
            diff = (x_dt - e_dt).total_seconds()
            if diff >= 0:
                holding_time_minutes = int(diff // 60)

        parsed_realized_r = None
        if realized_r and str(realized_r).strip():
            try:
                parsed_realized_r = float(str(realized_r).strip())
            except ValueError:
                pass

        trade.entry_date = parsed_date
        trade.entry_time = parsed_time
        trade.exit_date = parsed_exit_date
        trade.exit_time = parsed_exit_time
        trade.holding_time_minutes = holding_time_minutes
        trade.session_id = int(session_id) if session_id else auto_detect_session_id(db, entry_time)
        trade.instrument_id = final_instrument_id
        trade.strategy_id = int(strategy_id) if strategy_id else None
        trade.probability_level_id = int(probability_level_id) if probability_level_id else None
        trade.mtf_phase_id = int(mtf_phase_id) if mtf_phase_id else None
        trade.entry_news = entry_news or None
        trade.management_news = management_news or None
        trade.entry_candle_size = float(entry_candle_size) if entry_candle_size else None
        trade.adverse_wick_price = float(adverse_wick_price) if adverse_wick_price else None
        trade.mae_sl_buffer = float(mae_sl_buffer) if mae_sl_buffer else None
        trade.mfe = float(mfe) if mfe else None
        trade.comments = comments or None
        trade.execution_status = execution_status.strip().upper() if execution_status else "LIVE"
        trade.is_sl_swept = bool(is_sl_swept and is_sl_swept in ("1", "true", "True", "on", True))
        trade.outcome_type = outcome_type or "AUTO"
        trade.realized_r = parsed_realized_r
        trade.emotion_before = emotion_before.strip() if emotion_before else None
        trade.emotion_after = emotion_after.strip() if emotion_after else None

        if parsed_date:
            trade.day = parsed_date.day
            trade.day_of_week = parsed_date.weekday()
            trade.month_number = parsed_date.month
            trade.month_name = parsed_date.strftime("%B")
            trade.year = parsed_date.year
            trade.quarter = (parsed_date.month - 1) // 3 + 1

        # Re-sync all screenshots
        raw_urls = list(screenshots) if screenshots else []
        if screenshot_bulk:
            raw_urls.extend(re.split(r'[\r\n,]+', screenshot_bulk))
        for s_ind in [screenshot_1, screenshot_2, screenshot_3]:
            if s_ind and s_ind.strip():
                raw_urls.append(s_ind.strip())
        sync_trade_screenshots(db, trade, raw_urls, captions)
        if screenshot_1:
            trade.screenshot_1 = screenshot_1.strip()
        if screenshot_2:
            trade.screenshot_2 = screenshot_2.strip()
        if screenshot_3:
            trade.screenshot_3 = screenshot_3.strip()

        trade.max_r = compute_max_r(
            trade.entry_candle_size,
            trade.mfe,
            trade.mae_sl_buffer,
            inst.sl_buffer if inst else None,
        )
        if parsed_realized_r is not None:
            trade.fixed_r_target = parsed_realized_r
        else:
            trade.fixed_r_target = compute_fixed_r_target(
                trade.max_r,
                inst.fixed_r_target if inst else None,
            )

        db.commit()

        # Recalculate portfolio stats
        all_trades = db.query(Trade).order_by(Trade.id).all()
        for t in all_trades:
            _ = t.instrument_obj
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
        db.commit()

    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/{trade_id}/delete")
def delete_trade(request: Request, trade_id: int):
    with SessionLocal() as db:
        trade = db.query(Trade).get(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        db.delete(trade)
        db.commit()

        # Recalculate portfolio stats
        all_trades = db.query(Trade).order_by(Trade.id).all()
        for t in all_trades:
            _ = t.instrument_obj
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
        db.commit()

    return RedirectResponse(url="/trades/", status_code=303)


@router.post("/{trade_id}/upload_screenshot")
def upload_screenshot(
    request: Request,
    trade_id: int,
    screenshot: UploadFile = File(...),
    slot: str = Form("1"),
):
    with SessionLocal() as db:
        trade = db.query(Trade).get(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        ext = Path(screenshot.filename).suffix
        filename = f"trade_{trade_id}_slot{slot}{ext}"
        filepath = MEDIA_DIR / filename

        with open(filepath, "wb") as f:
            shutil.copyfileobj(screenshot.file, f)

        path_str = f"media/screenshots/{filename}"
        if slot == "1":
            trade.screenshot_1 = path_str
        elif slot == "2":
            trade.screenshot_2 = path_str
        elif slot == "3":
            trade.screenshot_3 = path_str

        db.commit()

    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/{trade_id}/set_screenshot_url")
def set_screenshot_url(
    request: Request,
    trade_id: int,
    url: str = Form(...),
    slot: str = Form("1"),
):
    with SessionLocal() as db:
        trade = db.query(Trade).get(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        url_clean = url.strip() if url else None
        if slot == "1":
            trade.screenshot_1 = url_clean
        elif slot == "2":
            trade.screenshot_2 = url_clean
        elif slot == "3":
            trade.screenshot_3 = url_clean

        db.commit()

    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/{trade_id}/add_screenshot")
def add_screenshot_to_trade(
    request: Request,
    trade_id: int,
    url: str = Form(""),
    caption: str = Form(""),
):
    with SessionLocal() as db:
        trade = db.query(Trade).get(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        if url and url.strip():
            count = db.query(TradeScreenshot).filter(TradeScreenshot.trade_id == trade_id).count()
            db.add(TradeScreenshot(trade_id=trade_id, url=url.strip(), caption=caption.strip() or None, order_index=count))
            if not trade.screenshot_1:
                trade.screenshot_1 = url.strip()
            elif not trade.screenshot_2:
                trade.screenshot_2 = url.strip()
            elif not trade.screenshot_3:
                trade.screenshot_3 = url.strip()
            db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


@router.post("/{trade_id}/delete_screenshot_item")
def delete_screenshot_item(
    request: Request,
    trade_id: int,
    screenshot_id: int = Form(...),
):
    with SessionLocal() as db:
        db.query(TradeScreenshot).filter(TradeScreenshot.id == screenshot_id, TradeScreenshot.trade_id == trade_id).delete()
        remaining = db.query(TradeScreenshot).filter(TradeScreenshot.trade_id == trade_id).order_by(TradeScreenshot.order_index).all()
        urls = [r.url for r in remaining]
        trade = db.query(Trade).get(trade_id)
        if trade:
            trade.screenshot_1 = urls[0] if len(urls) > 0 else None
            trade.screenshot_2 = urls[1] if len(urls) > 1 else None
            trade.screenshot_3 = urls[2] if len(urls) > 2 else None
        db.commit()
    return RedirectResponse(url=f"/trades/{trade_id}", status_code=303)


