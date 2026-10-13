import os
import re
import uuid
import base64
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, asc, func
from sqlalchemy.orm import selectinload

from database import SessionLocal
from models import (
    WatchlistIdea, Trade, Instrument, Session, Strategy, ProbabilityLevel, MTFPhase, TradeScreenshot,
)
from utils.template_helpers import format_time_12h, format_duration
from routers.trades import sync_trade_screenshots, auto_detect_session_id
from services.calculation_service import compute_portfolio_stats

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.filters["time_12h"] = format_time_12h
templates.env.filters["duration"] = format_duration

MEDIA_DIR = Path("media/screenshots")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

FINAL_OUTCOMES = {
    "FULL_TP",
    "FULL_SL",
    "BREAK_EVEN",
    "RUNNER",
    "TRAILING_STOP",
    "CUT_LOSS",
}


def is_closed_trade(trade):
    if not trade:
        return False
    if (trade.outcome_type or "AUTO").upper() in FINAL_OUTCOMES:
        return True
    return False


def trade_result_label(trade):
    if not trade:
        return "Needs Review"
    outcome = (trade.outcome_type or "AUTO").upper()
    if outcome != "AUTO":
        return outcome
    if trade.is_win is True:
        return "WIN"
    if trade.is_loss is True:
        return "LOSS"
    if trade.fixed_r_target == 0:
        return "BREAK_EVEN"
    return "Needs Review"


def save_base64_or_upload(image_data_str: str, file_upload: UploadFile = None, prefix: str = "wl") -> str:
    """Helper to save pasted base64 data URL or uploaded file into media/screenshots."""
    if file_upload and file_upload.filename:
        ext = Path(file_upload.filename).suffix.lower() or ".png"
        filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
        filepath = MEDIA_DIR / filename
        with open(filepath, "wb") as f:
            f.write(file_upload.file.read())
        return f"/media/screenshots/{filename}"

    if image_data_str and image_data_str.startswith("data:image/"):
        try:
            header, encoded = image_data_str.split(",", 1)
            ext = ".png"
            if "image/jpeg" in header or "image/jpg" in header:
                ext = ".jpg"
            elif "image/webp" in header:
                ext = ".webp"

            data = base64.b64decode(encoded)
            filename = f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
            filepath = MEDIA_DIR / filename
            with open(filepath, "wb") as f:
                f.write(data)
            return f"/media/screenshots/{filename}"
        except Exception as e:
            print(f"Failed to decode base64 image: {e}")

    # Return existing URL / TradingView link as is
    if image_data_str:
        return image_data_str.strip()
    return None


@router.get("/")
def watchlist_index(
    request: Request,
    status_filter: str = "ALL",
    scope_filter: str = "ALL",  # "ACTIVE", "ALL", "ARCHIVED"
    instrument_id: str = "",
    session_id: str = "",
    strategy_id: str = "",
    view_mode: str = "list",  # "list" or "grid"
    active_status: str = "ALL",
    view: str = "active",  # "active", "running", or "history"
    page: int = 1,
    per_page: int = 25,
):
    if view_mode not in {"list", "grid", "kanban"}:
        view_mode = "list"
    if view != "active" and view_mode == "kanban":
        view_mode = "list"
    active_status = active_status.upper() if active_status else "ALL"
    with SessionLocal() as db:
        instruments = db.query(Instrument).order_by(Instrument.name).all()
        sessions = db.query(Session).order_by(Session.name).all()
        strategies = db.query(Strategy).order_by(Strategy.is_active.desc(), Strategy.name.asc()).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        query = (
            db.query(WatchlistIdea)
            .options(
                selectinload(WatchlistIdea.instrument_obj),
                selectinload(WatchlistIdea.session_obj),
                selectinload(WatchlistIdea.strategy_obj),
                selectinload(WatchlistIdea.probability_level_obj),
                selectinload(WatchlistIdea.mtf_phase_obj),
                selectinload(WatchlistIdea.promoted_trade_obj),
            )
            .order_by(desc(WatchlistIdea.updated_at))
        )

        if status_filter and status_filter != "ALL":
            query = query.filter(WatchlistIdea.status == status_filter.upper())

        if instrument_id and instrument_id.isdigit():
            query = query.filter(WatchlistIdea.instrument_id == int(instrument_id))

        if session_id and session_id.isdigit():
            query = query.filter(WatchlistIdea.session_id == int(session_id))

        if strategy_id and strategy_id.isdigit():
            query = query.filter(WatchlistIdea.strategy_id == int(strategy_id))

        all_ideas = query.all()

        # Stats
        total_waiting = db.query(WatchlistIdea).filter(WatchlistIdea.status == "WAITING").count()
        total_monitoring = db.query(WatchlistIdea).filter(WatchlistIdea.status == "MONITORING").count()
        total_executed = db.query(WatchlistIdea).filter(WatchlistIdea.status == "EXECUTED").count()
        total_invalidated = db.query(WatchlistIdea).filter(WatchlistIdea.status.in_(["INVALIDATED", "RESOLVED"])).count()
        total_missed = db.query(WatchlistIdea).filter(WatchlistIdea.status == "MISSED").count()
        total_active = total_waiting + total_monitoring

        # Keep converted open trades separate from closed/history records.
        active_ideas = [
            i for i in all_ideas
            if i.status in {"WAITING", "MONITORING"}
            or (i.status == "EXECUTED" and not is_closed_trade(i.promoted_trade_obj))
        ]
        running_ideas = [
            i for i in all_ideas
            if i.status == "EXECUTED" and not is_closed_trade(i.promoted_trade_obj)
        ]
        history_ideas = [
            i for i in all_ideas
            if i.status in {"INVALIDATED", "MISSED", "RESOLVED"}
            or (
                i.status == "EXECUTED" and is_closed_trade(i.promoted_trade_obj)
            )
        ]

        if view == "running":
            display_ideas = running_ideas
        elif view == "history":
            display_ideas = history_ideas
        else:
            display_ideas = active_ideas

        # Legacy scope links still work, but the explicit tabs are the primary UI.
        if scope_filter == "ARCHIVED":
            view = "history"
            display_ideas = history_ideas
        elif scope_filter == "ACTIVE":
            view = "active"
            display_ideas = active_ideas

        if view == "active" and active_status != "ALL":
            status_map = {"WAITING": "WAITING", "MONITORING": "MONITORING", "RUNNING": "EXECUTED"}
            selected_status = status_map.get(active_status)
            if selected_status:
                display_ideas = [i for i in display_ideas if i.status == selected_status]

        # Kanban columns
        kanban = {
            "WAITING": [i for i in display_ideas if i.status == "WAITING"],
            "MONITORING": [i for i in display_ideas if i.status == "MONITORING"],
            "EXECUTED": [i for i in display_ideas if i.status == "EXECUTED"],
            "RESOLVED": [i for i in all_ideas if i.status in {"INVALIDATED", "MISSED", "RESOLVED"}],
        }

        total_history = len(history_ideas)
        total_running = len(running_ideas)
        total_pages = max(1, (total_history + per_page - 1) // per_page)
        page = max(1, min(page, total_pages))
        history_page = history_ideas[(page - 1) * per_page: page * per_page]

        # Query param messages
        msg = request.query_params.get("msg", "")
        error = request.query_params.get("error", "")

    return templates.TemplateResponse(
        request,
        "watchlist/index.html",
        {
            "ideas": display_ideas,
            "active_ideas": active_ideas,
            "running_ideas": running_ideas,
            "history_ideas": history_page,
            "kanban": kanban,
            "instruments": instruments,
            "sessions": sessions,
            "strategies": strategies,
            "probabilities": probabilities,
            "phases": phases,
            "total_active": total_active,
            "total_waiting": total_waiting,
            "total_monitoring": total_monitoring,
            "total_executed": total_executed,
            "total_running": total_running,
            "total_history": total_history,
            "total_invalidated": total_invalidated,
            "total_missed": total_missed,
            "status_filter": status_filter,
            "scope_filter": scope_filter,
            "instrument_id": instrument_id,
            "session_id": session_id,
            "strategy_id": strategy_id,
            "view_mode": view_mode,
            "active_status": active_status,
            "view": view,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
            "trade_result_label": trade_result_label,
            "msg": msg,
            "error": error,
        },
    )


@router.post("/{idea_id}/return-to-monitoring")
def return_to_monitoring(idea_id: int):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")
        if idea.status != "EXECUTED" or not idea.promoted_trade_id:
            raise HTTPException(status_code=400, detail="Only a linked running trade can return to monitoring")
        trade = db.get(Trade, idea.promoted_trade_id)
        if is_closed_trade(trade):
            raise HTTPException(status_code=400, detail="Closed trades cannot return to monitoring")
        idea.promoted_trade_id = None
        idea.status = "MONITORING"
        db.commit()
    return RedirectResponse(url="/watchlist/?view=active&msg=Setup+returned+to+Monitoring", status_code=303)


@router.post("/{idea_id}/archive")
def archive_watchlist_idea(idea_id: int):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")
        idea.status = "RESOLVED"
        idea.resolved_at = datetime.now()
        db.commit()
    return RedirectResponse(url="/watchlist/?msg=Idea+archived+successfully", status_code=303)


@router.post("/{idea_id}/restore")
def restore_watchlist_idea(idea_id: int):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")
        idea.status = "EXECUTED" if idea.promoted_trade_id else "WAITING"
        db.commit()
    return RedirectResponse(url="/watchlist/?msg=Idea+restored+to+active+board", status_code=303)


@router.get("/new")
def watchlist_new_form(request: Request):
    with SessionLocal() as db:
        instruments = db.query(Instrument).order_by(Instrument.name).all()
        sessions = db.query(Session).order_by(Session.name).all()
        strategies = db.query(Strategy).order_by(Strategy.is_active.desc(), Strategy.name.asc()).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        return templates.TemplateResponse(
            request,
            "watchlist/form.html",
            {
                "idea": None,
                "instruments": instruments,
                "sessions": sessions,
                "strategies": strategies,
                "probabilities": probabilities,
                "phases": phases,
            },
        )


@router.post("/new")
def create_watchlist_idea(
    title: str = Form(""),
    instrument_id: str = Form(""),
    session_id: str = Form(""),
    strategy_id: str = Form(""),
    probability_level_id: str = Form(""),
    mtf_phase_id: str = Form(""),
    direction: str = Form("LONG"),
    planned_entry: str = Form(""),
    planned_sl: str = Form(""),
    planned_tp: str = Form(""),
    planned_rr: str = Form(""),
    htf_bias: str = Form(""),
    ltf_confirmation: str = Form(""),
    notes: str = Form(""),
    htf_image_url: str = Form(""),
    ltf_image_url: str = Form(""),
    tradingview_url: str = Form(""),
    timeframe_layers_json: str = Form("[]"),
    status: str = Form("WAITING"),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
):
    with SessionLocal() as db:
        title = title.strip()
        if not title:
            pair_name = ""
            if instrument_id and instrument_id.isdigit():
                inst = db.query(Instrument).get(int(instrument_id))
                if inst:
                    pair_name = inst.name
            title = f"{pair_name or 'Market'} {direction} Setup".strip()

        # Parse timeframe layers JSON if provided
        import json
        layers_data = []
        if timeframe_layers_json and timeframe_layers_json.strip():
            try:
                parsed = json.loads(timeframe_layers_json)
                if isinstance(parsed, list):
                    for layer in parsed:
                        img = layer.get("image_url", "").strip()
                        if img:
                            img = save_base64_or_upload(img, prefix="tf")
                        layers_data.append({
                            "title": layer.get("title", "").strip(),
                            "image_url": img,
                            "tv_url": layer.get("tv_url", "").strip(),
                            "note": layer.get("note", "").strip(),
                        })
            except Exception:
                pass

        # Handle pasted images / URLs (or fallback from layers)
        htf_final = save_base64_or_upload(htf_image_url, prefix="htf") if htf_image_url else None
        ltf_final = save_base64_or_upload(ltf_image_url, prefix="ltf") if ltf_image_url else None

        if layers_data:
            if not htf_final and len(layers_data) > 0 and layers_data[0].get("image_url"):
                htf_final = layers_data[0].get("image_url")
            if not ltf_final and len(layers_data) > 1 and layers_data[1].get("image_url"):
                ltf_final = layers_data[1].get("image_url")
            if not tradingview_url and len(layers_data) > 0 and layers_data[0].get("tv_url"):
                tradingview_url = layers_data[0].get("tv_url")

        def parse_float(val):
            try:
                return float(val.strip()) if val and val.strip() else None
            except Exception:
                return None

        p_entry = parse_float(planned_entry)
        p_sl = parse_float(planned_sl)
        p_tp = parse_float(planned_tp)
        p_rr = parse_float(planned_rr)

        if p_rr is None and p_entry is not None and p_sl is not None and p_tp is not None:
            risk = abs(p_entry - p_sl)
            reward = abs(p_tp - p_entry)
            if risk > 0:
                p_rr = round(reward / risk, 2)

        idea = WatchlistIdea(
            title=title,
            instrument_id=int(instrument_id) if instrument_id and instrument_id.isdigit() else None,
            session_id=int(session_id) if session_id and session_id.isdigit() else None,
            strategy_id=int(strategy_id) if strategy_id and strategy_id.isdigit() else None,
            probability_level_id=int(probability_level_id) if probability_level_id and probability_level_id.isdigit() else None,
            mtf_phase_id=int(mtf_phase_id) if mtf_phase_id and mtf_phase_id.isdigit() else None,
            direction=direction.upper() if direction else "LONG",
            planned_entry=p_entry,
            planned_sl=p_sl,
            planned_tp=p_tp,
            planned_rr=p_rr,
            htf_bias=htf_bias.strip() if htf_bias else None,
            ltf_confirmation=ltf_confirmation.strip() if ltf_confirmation else None,
            notes=notes.strip() if notes else None,
            htf_image_url=htf_final,
            ltf_image_url=ltf_final,
            tradingview_url=tradingview_url.strip() if tradingview_url else None,
            timeframe_layers=json.dumps(layers_data) if layers_data else None,
            status=status.upper() if status else "WAITING",
        )
        db.add(idea)
        db.commit()
        db.refresh(idea)

        if status.upper() == "EXECUTED" and entry_time and entry_time.strip():
            if not entry_date or not entry_date.strip():
                entry_date = datetime.now().strftime("%Y-%m-%d")
            create_live_trade_from_idea(
                db=db,
                idea=idea,
                entry_date_str=entry_date.strip(),
                entry_time_str=entry_time.strip(),
                entry_price_str=str(p_entry) if p_entry is not None else "",
                stop_loss_str=str(p_sl) if p_sl is not None else "",
                take_profit_str=str(p_tp) if p_tp is not None else "",
                session_id_str=session_id,
                strategy_id_str=strategy_id,
                probability_id_str=probability_level_id,
                phase_id_str=mtf_phase_id,
                comments_str="",
            )

    return RedirectResponse(url=f"/watchlist/?msg=Setup+{quote(title)}+added+to+Watchlist", status_code=303)


@router.get("/{idea_id}")
def watchlist_detail(request: Request, idea_id: int):
    with SessionLocal() as db:
        idea = (
            db.query(WatchlistIdea)
            .options(
                selectinload(WatchlistIdea.instrument_obj),
                selectinload(WatchlistIdea.session_obj),
                selectinload(WatchlistIdea.strategy_obj),
                selectinload(WatchlistIdea.probability_level_obj),
                selectinload(WatchlistIdea.mtf_phase_obj),
                selectinload(WatchlistIdea.promoted_trade_obj),
            )
            .get(idea_id)
        )
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        sessions = db.query(Session).order_by(Session.name).all()
        strategies = db.query(Strategy).order_by(Strategy.is_active.desc(), Strategy.name.asc()).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        return templates.TemplateResponse(
            request,
            "watchlist/detail.html",
            {
                "idea": idea,
                "sessions": sessions,
                "strategies": strategies,
                "probabilities": probabilities,
                "phases": phases,
            },
        )


@router.get("/{idea_id}/edit")
def watchlist_edit_form(request: Request, idea_id: int):
    with SessionLocal() as db:
        idea = (
            db.query(WatchlistIdea)
            .options(
                selectinload(WatchlistIdea.promoted_trade_obj)
            )
            .get(idea_id)
        )
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        instruments = db.query(Instrument).order_by(Instrument.name).all()
        sessions = db.query(Session).order_by(Session.name).all()
        strategies = db.query(Strategy).order_by(Strategy.is_active.desc(), Strategy.name.asc()).all()
        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()

        return templates.TemplateResponse(
            request,
            "watchlist/form.html",
            {
                "idea": idea,
                "instruments": instruments,
                "sessions": sessions,
                "strategies": strategies,
                "probabilities": probabilities,
                "phases": phases,
            },
        )


@router.post("/{idea_id}/edit")
def update_watchlist_idea(
    idea_id: int,
    title: str = Form(""),
    instrument_id: str = Form(""),
    session_id: str = Form(""),
    strategy_id: str = Form(""),
    probability_level_id: str = Form(""),
    mtf_phase_id: str = Form(""),
    direction: str = Form("LONG"),
    planned_entry: str = Form(""),
    planned_sl: str = Form(""),
    planned_tp: str = Form(""),
    planned_rr: str = Form(""),
    htf_bias: str = Form(""),
    ltf_confirmation: str = Form(""),
    notes: str = Form(""),
    htf_image_url: str = Form(""),
    ltf_image_url: str = Form(""),
    tradingview_url: str = Form(""),
    timeframe_layers_json: str = Form("[]"),
    status: str = Form("WAITING"),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        # Parse timeframe layers JSON
        import json
        layers_data = []
        if timeframe_layers_json and timeframe_layers_json.strip():
            try:
                parsed = json.loads(timeframe_layers_json)
                if isinstance(parsed, list):
                    for layer in parsed:
                        img = layer.get("image_url", "").strip()
                        if img:
                            img = save_base64_or_upload(img, prefix="tf")
                        layers_data.append({
                            "title": layer.get("title", "").strip(),
                            "image_url": img,
                            "tv_url": layer.get("tv_url", "").strip(),
                            "note": layer.get("note", "").strip(),
                        })
            except Exception:
                pass

        if layers_data:
            idea.timeframe_layers = json.dumps(layers_data)
            if len(layers_data) > 0 and layers_data[0].get("image_url"):
                idea.htf_image_url = layers_data[0].get("image_url")
            if len(layers_data) > 1 and layers_data[1].get("image_url"):
                idea.ltf_image_url = layers_data[1].get("image_url")
            if len(layers_data) > 0 and layers_data[0].get("tv_url"):
                idea.tradingview_url = layers_data[0].get("tv_url")

        def parse_float(val):
            try:
                return float(val.strip()) if val and val.strip() else None
            except Exception:
                return None

        p_entry = parse_float(planned_entry)
        p_sl = parse_float(planned_sl)
        p_tp = parse_float(planned_tp)
        p_rr = parse_float(planned_rr)

        if p_rr is None and p_entry is not None and p_sl is not None and p_tp is not None:
            risk = abs(p_entry - p_sl)
            reward = abs(p_tp - p_entry)
            if risk > 0:
                p_rr = round(reward / risk, 2)

        idea.title = title.strip() if title.strip() else idea.title
        idea.instrument_id = int(instrument_id) if instrument_id and instrument_id.isdigit() else None
        idea.session_id = int(session_id) if session_id and session_id.isdigit() else None
        idea.strategy_id = int(strategy_id) if strategy_id and strategy_id.isdigit() else None
        idea.probability_level_id = int(probability_level_id) if probability_level_id and probability_level_id.isdigit() else None
        idea.mtf_phase_id = int(mtf_phase_id) if mtf_phase_id and mtf_phase_id.isdigit() else None
        idea.direction = direction.upper() if direction else "LONG"
        idea.planned_entry = p_entry
        idea.planned_sl = p_sl
        idea.planned_tp = p_tp
        idea.planned_rr = p_rr
        idea.htf_bias = htf_bias.strip() if htf_bias else None
        idea.ltf_confirmation = ltf_confirmation.strip() if ltf_confirmation else None
        idea.notes = notes.strip() if notes else None

        if htf_image_url:
            idea.htf_image_url = save_base64_or_upload(htf_image_url, prefix="htf")
        if ltf_image_url:
            idea.ltf_image_url = save_base64_or_upload(ltf_image_url, prefix="ltf")
        if tradingview_url:
            idea.tradingview_url = tradingview_url.strip()

        old_status = idea.status
        new_status = status.upper() if status else "WAITING"
        idea.status = new_status

        if new_status in {"INVALIDATED", "MISSED", "RESOLVED"} and old_status not in {"INVALIDATED", "MISSED", "RESOLVED"}:
            idea.resolved_at = datetime.now()

        # If updated to EXECUTED and timing is provided
        if new_status == "EXECUTED" and not idea.promoted_trade_id and entry_time and entry_time.strip():
            if not entry_date or not entry_date.strip():
                entry_date = datetime.now().strftime("%Y-%m-%d")
            create_live_trade_from_idea(
                db=db,
                idea=idea,
                entry_date_str=entry_date.strip(),
                entry_time_str=entry_time.strip(),
                entry_price_str=str(p_entry) if p_entry is not None else "",
                stop_loss_str=str(p_sl) if p_sl is not None else "",
                take_profit_str=str(p_tp) if p_tp is not None else "",
                session_id_str=session_id,
                strategy_id_str=strategy_id,
                probability_id_str=probability_level_id,
                phase_id_str=mtf_phase_id,
                comments_str="",
            )
        elif new_status == "EXECUTED" and idea.promoted_trade_id and entry_time and entry_time.strip():
            promoted_trade = db.query(Trade).get(idea.promoted_trade_id)
            if promoted_trade:
                if entry_date and entry_date.strip():
                    try:
                        promoted_trade.entry_date = datetime.strptime(entry_date.strip(), "%Y-%m-%d").date()
                    except Exception:
                        pass
                try:
                    promoted_trade.entry_time = datetime.strptime(entry_time.strip()[:5], "%H:%M").time()
                except Exception:
                    pass

        saved_title = str(idea.title)
        db.commit()

    return RedirectResponse(url=f"/watchlist/?msg=Setup+{quote(saved_title)}+updated", status_code=303)


def create_live_trade_from_idea(
    db,
    idea: WatchlistIdea,
    entry_date_str: str,
    entry_time_str: str,
    entry_price_str: str = "",
    stop_loss_str: str = "",
    take_profit_str: str = "",
    session_id_str: str = "",
    strategy_id_str: str = "",
    probability_id_str: str = "",
    phase_id_str: str = "",
    comments_str: str = "",
) -> Trade:
    if not entry_date_str or not entry_date_str.strip():
        raise ValueError("Start Date is required to convert into a live trade.")
    if not entry_time_str or not entry_time_str.strip():
        raise ValueError("Start Time is required to convert into a live trade.")

    parsed_date = datetime.strptime(entry_date_str.strip(), "%Y-%m-%d").date()
    parsed_time = datetime.strptime(entry_time_str.strip()[:5], "%H:%M").time()

    def parse_float(val):
        try:
            return float(str(val).strip()) if val and str(val).strip() else None
        except Exception:
            return None

    p_entry = parse_float(entry_price_str) if entry_price_str else idea.planned_entry
    p_sl = parse_float(stop_loss_str) if stop_loss_str else idea.planned_sl
    p_tp = parse_float(take_profit_str) if take_profit_str else idea.planned_tp

    candle_size = None
    if p_entry is not None and p_sl is not None:
        candle_size = round(abs(p_entry - p_sl), 5)

    fixed_r = idea.planned_rr
    if fixed_r is None and p_entry is not None and p_sl is not None and p_tp is not None and candle_size and candle_size > 0:
        fixed_r = round(abs(p_tp - p_entry) / candle_size, 2)

    final_session_id = None
    if session_id_str and str(session_id_str).isdigit():
        final_session_id = int(session_id_str)
    elif idea.session_id:
        final_session_id = idea.session_id
    else:
        final_session_id = auto_detect_session_id(db, entry_time_str.strip()[:5])

    final_strategy_id = int(strategy_id_str) if strategy_id_str and str(strategy_id_str).isdigit() else idea.strategy_id
    final_probability_id = int(probability_id_str) if probability_id_str and str(probability_id_str).isdigit() else idea.probability_level_id
    final_phase_id = int(phase_id_str) if phase_id_str and str(phase_id_str).isdigit() else idea.mtf_phase_id

    # Extract layer screenshots & notes
    layer_items = []
    if idea.layers_list:
        for idx, lyr in enumerate(idea.layers_list, 1):
            shot = (lyr.get("image_url") or lyr.get("tv_url") or "").strip()
            title = (lyr.get("title") or f"Layer #{idx}").strip()
            if shot:
                layer_items.append((shot, title))

    if not layer_items:
        for idx, raw in enumerate([idea.htf_image_url, idea.ltf_image_url, idea.tradingview_url], 1):
            if raw and raw.strip():
                layer_items.append((raw.strip(), f"Chart #{idx}"))

    notes_sections = []
    if comments_str and comments_str.strip():
        notes_sections.append(comments_str.strip())
    else:
        if idea.notes and idea.notes.strip():
            notes_sections.append(f"📌 General Trade Plan:\n{idea.notes.strip()}")
        layer_notes = []
        if idea.layers_list:
            for idx, lyr in enumerate(idea.layers_list, 1):
                lyr_title = lyr.get("title") or f"Layer #{idx}"
                lyr_note = lyr.get("note") or ""
                if lyr_note and lyr_note.strip():
                    layer_notes.append(f"• [{lyr_title}]: {lyr_note.strip()}")
        if layer_notes:
            notes_sections.append("🎯 Timeframe Analysis & Bias:\n" + "\n".join(layer_notes))

    combined_notes = "\n\n".join(notes_sections) if notes_sections else f"Converted from Watchlist: {idea.title}"

    trade = Trade(
        entry_date=parsed_date,
        entry_time=parsed_time,
        session_id=final_session_id,
        instrument_id=idea.instrument_id,
        strategy_id=final_strategy_id,
        probability_level_id=final_probability_id,
        mtf_phase_id=final_phase_id,
        direction=idea.direction or "LONG",
        entry_price=p_entry,
        stop_loss=p_sl,
        take_profit=p_tp,
        entry_candle_size=candle_size,
        fixed_r_target=fixed_r,
        comments=combined_notes,
        execution_status="LIVE",
        outcome_type="AUTO",
    )
    trade.day = parsed_date.day
    trade.day_of_week = parsed_date.weekday()
    trade.month_number = parsed_date.month
    trade.month_name = parsed_date.strftime("%B")
    trade.year = parsed_date.year
    trade.quarter = (parsed_date.month - 1) // 3 + 1

    db.add(trade)
    db.commit()
    db.refresh(trade)

    raw_urls = [s_url for s_url, _ in layer_items]
    raw_captions = [s_cap for _, s_cap in layer_items]
    sync_trade_screenshots(db, trade, raw_urls, raw_captions)

    idea.promoted_trade_id = trade.id
    idea.status = "EXECUTED"
    idea.resolved_at = datetime.now()
    db.commit()

    all_trades = db.query(Trade).order_by(Trade.id).all()
    for t in all_trades:
        _ = t.instrument_obj
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

    return trade


@router.post("/{idea_id}/status")
def quick_update_status(
    idea_id: int,
    status: str = Form(...),
    entry_date: str = Form(""),
    entry_time: str = Form(""),
):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        old_status = idea.status
        new_status = status.upper().strip()
        idea.status = new_status

        if new_status in {"INVALIDATED", "MISSED", "RESOLVED"} and old_status not in {"INVALIDATED", "MISSED", "RESOLVED"}:
            idea.resolved_at = datetime.now()

        # If converted to EXECUTED and not yet promoted to a trade
        if new_status == "EXECUTED" and not idea.promoted_trade_id:
            if entry_date.strip() and entry_time.strip():
                try:
                    create_live_trade_from_idea(db, idea, entry_date, entry_time)
                    return RedirectResponse(
                        url=f"/watchlist/?msg=Setup+converted+to+Live+Trade+#{idea.promoted_trade_id}",
                        status_code=303
                    )
                except Exception as e:
                    return RedirectResponse(
                        url=f"/watchlist/?convert_id={idea_id}&error={quote(str(e))}",
                        status_code=303
                    )

        db.commit()

    return RedirectResponse(url=f"/watchlist/?msg=Status+updated+to+{new_status}", status_code=303)


@router.post("/{idea_id}/convert-to-trade")
def convert_watchlist_to_trade(
    idea_id: int,
    entry_date: str = Form(""),
    entry_time: str = Form(""),
    entry_price: str = Form(""),
    stop_loss: str = Form(""),
    take_profit: str = Form(""),
    session_id: str = Form(""),
    strategy_id: str = Form(""),
    probability_level_id: str = Form(""),
    mtf_phase_id: str = Form(""),
    comments: str = Form(""),
):
    with SessionLocal() as db:
        idea = (
            db.query(WatchlistIdea)
            .options(
                selectinload(WatchlistIdea.instrument_obj),
                selectinload(WatchlistIdea.session_obj),
                selectinload(WatchlistIdea.strategy_obj),
            )
            .get(idea_id)
        )
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        if not entry_date.strip() or not entry_time.strip():
            return RedirectResponse(
                url=f"/watchlist/?convert_id={idea_id}&error=Start+Date+and+Start+Time+are+strictly+required+to+insert+into+Live+Trades",
                status_code=303
            )

        if idea.promoted_trade_id:
            return RedirectResponse(
                url=f"/watchlist/?msg=Setup+is+already+logged+in+Trade+#{idea.promoted_trade_id}",
                status_code=303
            )

        try:
            trade = create_live_trade_from_idea(
                db,
                idea,
                entry_date_str=entry_date,
                entry_time_str=entry_time,
                entry_price_str=entry_price,
                stop_loss_str=stop_loss,
                take_profit_str=take_profit,
                session_id_str=session_id,
                strategy_id_str=strategy_id,
                probability_id_str=probability_level_id,
                phase_id_str=mtf_phase_id,
                comments_str=comments,
            )
            trade_num = trade.id
        except Exception as e:
            return RedirectResponse(
                url=f"/watchlist/?convert_id={idea_id}&error={quote(str(e))}",
                status_code=303
            )

    return RedirectResponse(
        url=f"/watchlist/?msg=Live+Trade+#{trade_num}+created+and+linked+successfully!",
        status_code=303
    )


@router.get("/{idea_id}/promote")
def promote_idea_to_trade(idea_id: int):
    """
    1-Click Promote: Prepopulates the official Trade Log form (/trades/new) with 
    all data from this watchlist setup (Pair, Session, Strategy, Prices, HTF/LTF images, notes).
    """
    with SessionLocal() as db:
        idea = (
            db.query(WatchlistIdea)
            .options(
                selectinload(WatchlistIdea.instrument_obj),
                selectinload(WatchlistIdea.session_obj),
                selectinload(WatchlistIdea.strategy_obj),
            )
            .get(idea_id)
        )
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        # Extract multi-timeframe layer screenshots and titles in exact order
        layer_items = []
        if idea.layers_list:
            for idx, lyr in enumerate(idea.layers_list, 1):
                shot = (lyr.get("image_url") or lyr.get("tv_url") or "").strip()
                title = (lyr.get("title") or f"Layer #{idx}").strip()
                if shot:
                    layer_items.append((shot, title))

        if not layer_items:
            for idx, raw in enumerate([idea.htf_image_url, idea.ltf_image_url, idea.tradingview_url], 1):
                if raw and raw.strip():
                    layer_items.append((raw.strip(), f"Chart #{idx}"))

        # Build comprehensive execution notes from general notes + all timeframe layer notes
        notes_sections = []
        if idea.notes and idea.notes.strip():
            notes_sections.append(f"📌 General Trade Plan:\n{idea.notes.strip()}")

        layer_notes = []
        if idea.layers_list:
            for idx, lyr in enumerate(idea.layers_list, 1):
                lyr_title = lyr.get("title") or f"Layer #{idx}"
                lyr_note = lyr.get("note") or ""
                if lyr_note and lyr_note.strip():
                    layer_notes.append(f"• [{lyr_title}]: {lyr_note.strip()}")

        if layer_notes:
            notes_sections.append("🎯 Timeframe Analysis & Bias:\n" + "\n".join(layer_notes))

        if not notes_sections:
            combined_notes = f"Promoted from Watchlist: {idea.title}"
        else:
            combined_notes = "\n\n".join(notes_sections)

        today_str = datetime.now().strftime("%Y-%m-%d")
        now_str = datetime.now().strftime("%H:%M")

        # Build pre-fill URL parameters
        params = {
            "from_watchlist_id": idea.id,
            "entry_date": idea.resolved_at.strftime("%Y-%m-%d") if idea.resolved_at else today_str,
            "entry_time": now_str,
            "instrument_id": idea.instrument_id or "",
            "session_id": idea.session_id or "",
            "strategy_id": idea.strategy_id or "",
            "probability_level_id": idea.probability_level_id or "",
            "mtf_phase_id": idea.mtf_phase_id or "",
            "direction": idea.direction or "LONG",
            "entry_price": idea.planned_entry or "",
            "stop_loss": idea.planned_sl or "",
            "tp_target": idea.planned_tp or "",
            "fixed_r_target": idea.planned_rr or "",
            "notes": combined_notes,
        }

        for i, (s_url, s_cap) in enumerate(layer_items, 1):
            params[f"screenshot_{i}"] = s_url
            params[f"caption_{i}"] = s_cap

        query_string = urlencode({k: v for k, v in params.items() if v is not None and v != ""})
        return RedirectResponse(url=f"/trades/new?{query_string}", status_code=303)


@router.post("/{idea_id}/delete")
def delete_watchlist_idea(idea_id: int):
    with SessionLocal() as db:
        idea = db.query(WatchlistIdea).get(idea_id)
        if not idea:
            raise HTTPException(status_code=404, detail="Watchlist Idea not found")

        title = idea.title
        db.delete(idea)
        db.commit()

    return RedirectResponse(url=f"/watchlist/?msg=Setup+{quote(title)}+deleted", status_code=303)


@router.post("/api/upload_image")
async def api_upload_image(request: Request, image: UploadFile = File(...)):
    """Fast AJAX endpoint for pasted images from clipboard."""
    if not image or not image.filename:
        raise HTTPException(status_code=400, detail="No image file provided")

    ext = Path(image.filename).suffix.lower() or ".png"
    filename = f"wl_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}{ext}"
    filepath = MEDIA_DIR / filename

    content = await image.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return JSONResponse({
        "status": "success",
        "url": f"/media/screenshots/{filename}",
        "filename": filename,
    })
