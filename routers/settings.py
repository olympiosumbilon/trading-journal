from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import selectinload
from urllib.parse import quote
import re
from database import SessionLocal
from models import Instrument, Session, Strategy, ProbabilityLevel, MTFPhase, Trade
from services.calculation_service import (
    compute_max_r, compute_fixed_r_target, compute_portfolio_stats,
)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def generate_slug(name: str, model_cls, db, existing_id=None) -> str:
    base_slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")
    if not base_slug:
        base_slug = "item"
    slug = base_slug
    counter = 1
    while True:
        query = db.query(model_cls).filter(model_cls.slug == slug)
        if existing_id:
            query = query.filter(model_cls.id != existing_id)
        if not query.first():
            break
        counter += 1
        slug = f"{base_slug}_{counter}"
    return slug


def recalc_all(db):
    """Recompute all trade stats after a settings change."""
    trades = db.query(Trade).order_by(Trade.id).all()
    for t in trades:
        _ = t.instrument_obj
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


@router.get("/")
def settings_index(request: Request, msg: str = "", error: str = ""):
    with SessionLocal() as db:
        instruments = db.query(Instrument).order_by(Instrument.name).all()
        for inst in instruments:
            inst.trade_count = db.query(Trade).filter(Trade.instrument_id == inst.id).count()

        sessions = db.query(Session).order_by(Session.name).all()
        for s in sessions:
            s.trade_count = db.query(Trade).filter(Trade.session_id == s.id).count()

        strategies = db.query(Strategy).order_by(Strategy.name).all()
        for st in strategies:
            st.trade_count = db.query(Trade).filter(Trade.strategy_id == st.id).count()

        probabilities = db.query(ProbabilityLevel).order_by(ProbabilityLevel.name).all()
        for p in probabilities:
            p.trade_count = db.query(Trade).filter(Trade.probability_level_id == p.id).count()

        phases = db.query(MTFPhase).order_by(MTFPhase.name).all()
        for ph in phases:
            ph.trade_count = db.query(Trade).filter(Trade.mtf_phase_id == ph.id).count()

    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "instruments": instruments,
            "sessions": sessions,
            "strategies": strategies,
            "probabilities": probabilities,
            "phases": phases,
            "msg": msg,
            "error": error,
        },
    )


# --- INSTRUMENTS ---

@router.post("/instrument/new")
def create_instrument(
    name: str = Form(""),
    sl_buffer: str = Form(""),
    fixed_r_target: str = Form(""),
):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Instrument+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        slug = generate_slug(name, Instrument, db)
        inst = Instrument(
            name=name,
            slug=slug,
            sl_buffer=float(sl_buffer) if sl_buffer else None,
            fixed_r_target=float(fixed_r_target) if fixed_r_target else None,
        )
        db.add(inst)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Instrument+{quote(name)}+added+successfully", status_code=303)


@router.post("/instrument/{instrument_id}")
def update_instrument(
    instrument_id: int,
    name: str = Form(""),
    sl_buffer: str = Form(""),
    fixed_r_target: str = Form(""),
):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Instrument+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        inst = db.query(Instrument).get(instrument_id)
        if not inst:
            raise HTTPException(status_code=404, detail="Instrument not found")

        inst.name = name
        inst.slug = generate_slug(name, Instrument, db, existing_id=instrument_id)
        inst.sl_buffer = float(sl_buffer) if sl_buffer else None
        inst.fixed_r_target = float(fixed_r_target) if fixed_r_target else None
        db.commit()

        # Recompute max_r and fixed_r_target for trades of this instrument
        affected = db.query(Trade).filter(Trade.instrument_id == instrument_id).all()
        for t in affected:
            t.max_r = compute_max_r(
                t.entry_candle_size, t.mfe, t.mae_sl_buffer, inst.sl_buffer,
            )
            t.fixed_r_target = compute_fixed_r_target(
                t.max_r, inst.fixed_r_target,
            )
        db.commit()

        # Recompute portfolio stats
        recalc_all(db)

    return RedirectResponse(url=f"/settings/?msg=Instrument+{quote(name)}+updated", status_code=303)


@router.post("/instrument/{instrument_id}/delete")
def delete_instrument(instrument_id: int):
    with SessionLocal() as db:
        inst = db.query(Instrument).get(instrument_id)
        if not inst:
            raise HTTPException(status_code=404, detail="Instrument not found")

        trade_count = db.query(Trade).filter(Trade.instrument_id == instrument_id).count()
        if trade_count > 0:
            return RedirectResponse(
                url=f"/settings/?error=Cannot+delete+{quote(inst.name)}+because+it+is+used+by+{trade_count}+trade(s)",
                status_code=303,
            )

        name = inst.name
        db.delete(inst)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Instrument+{quote(name)}+removed", status_code=303)


# --- SESSIONS ---

@router.post("/session/new")
def create_session(name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Session+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        slug = generate_slug(name, Session, db)
        s = Session(name=name, slug=slug)
        db.add(s)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Session+{quote(name)}+added", status_code=303)


@router.post("/session/{session_id}")
def update_session(session_id: int, name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Session+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        s = db.query(Session).get(session_id)
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")
        s.name = name
        s.slug = generate_slug(name, Session, db, existing_id=session_id)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Session+{quote(name)}+updated", status_code=303)


@router.post("/session/{session_id}/delete")
def delete_session(session_id: int):
    with SessionLocal() as db:
        s = db.query(Session).get(session_id)
        if not s:
            raise HTTPException(status_code=404, detail="Session not found")

        trade_count = db.query(Trade).filter(Trade.session_id == session_id).count()
        if trade_count > 0:
            return RedirectResponse(
                url=f"/settings/?error=Cannot+delete+{quote(s.name)}+because+it+is+used+by+{trade_count}+trade(s)",
                status_code=303,
            )

        name = s.name
        db.delete(s)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Session+{quote(name)}+removed", status_code=303)


# --- STRATEGIES ---

@router.post("/strategy/new")
def create_strategy(name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Strategy+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        slug = generate_slug(name, Strategy, db)
        st = Strategy(name=name, slug=slug)
        db.add(st)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Strategy+{quote(name)}+added", status_code=303)


@router.post("/strategy/{strategy_id}")
def update_strategy(strategy_id: int, name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Strategy+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        st = db.query(Strategy).get(strategy_id)
        if not st:
            raise HTTPException(status_code=404, detail="Strategy not found")
        st.name = name
        st.slug = generate_slug(name, Strategy, db, existing_id=strategy_id)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Strategy+{quote(name)}+updated", status_code=303)


@router.post("/strategy/{strategy_id}/delete")
def delete_strategy(strategy_id: int):
    with SessionLocal() as db:
        st = db.query(Strategy).get(strategy_id)
        if not st:
            raise HTTPException(status_code=404, detail="Strategy not found")

        trade_count = db.query(Trade).filter(Trade.strategy_id == strategy_id).count()
        if trade_count > 0:
            return RedirectResponse(
                url=f"/settings/?error=Cannot+delete+{quote(st.name)}+because+it+is+used+by+{trade_count}+trade(s)",
                status_code=303,
            )

        name = st.name
        db.delete(st)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Strategy+{quote(name)}+removed", status_code=303)


# --- PROBABILITIES ---

@router.post("/probability/new")
def create_probability(name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Probability+level+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        slug = generate_slug(name, ProbabilityLevel, db)
        p = ProbabilityLevel(name=name, slug=slug)
        db.add(p)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Probability+Level+{quote(name)}+added", status_code=303)


@router.post("/probability/{probability_id}")
def update_probability(probability_id: int, name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=Probability+level+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        p = db.query(ProbabilityLevel).get(probability_id)
        if not p:
            raise HTTPException(status_code=404, detail="Probability level not found")
        p.name = name
        p.slug = generate_slug(name, ProbabilityLevel, db, existing_id=probability_id)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Probability+Level+{quote(name)}+updated", status_code=303)


@router.post("/probability/{probability_id}/delete")
def delete_probability(probability_id: int):
    with SessionLocal() as db:
        p = db.query(ProbabilityLevel).get(probability_id)
        if not p:
            raise HTTPException(status_code=404, detail="Probability level not found")

        trade_count = db.query(Trade).filter(Trade.probability_level_id == probability_id).count()
        if trade_count > 0:
            return RedirectResponse(
                url=f"/settings/?error=Cannot+delete+{quote(p.name)}+because+it+is+used+by+{trade_count}+trade(s)",
                status_code=303,
            )

        name = p.name
        db.delete(p)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=Probability+Level+{quote(name)}+removed", status_code=303)


# --- PHASES ---

@router.post("/phase/new")
def create_phase(name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=MTF+Phase+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        slug = generate_slug(name, MTFPhase, db)
        ph = MTFPhase(name=name, slug=slug)
        db.add(ph)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=MTF+Phase+{quote(name)}+added", status_code=303)


@router.post("/phase/{phase_id}")
def update_phase(phase_id: int, name: str = Form("")):
    name = name.strip()
    if not name:
        return RedirectResponse(url="/settings/?error=MTF+Phase+name+cannot+be+empty", status_code=303)

    with SessionLocal() as db:
        ph = db.query(MTFPhase).get(phase_id)
        if not ph:
            raise HTTPException(status_code=404, detail="MTF phase not found")
        ph.name = name
        ph.slug = generate_slug(name, MTFPhase, db, existing_id=phase_id)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=MTF+Phase+{quote(name)}+updated", status_code=303)


@router.post("/phase/{phase_id}/delete")
def delete_phase(phase_id: int):
    with SessionLocal() as db:
        ph = db.query(MTFPhase).get(phase_id)
        if not ph:
            raise HTTPException(status_code=404, detail="MTF phase not found")

        trade_count = db.query(Trade).filter(Trade.mtf_phase_id == phase_id).count()
        if trade_count > 0:
            return RedirectResponse(
                url=f"/settings/?error=Cannot+delete+{quote(ph.name)}+because+it+is+used+by+{trade_count}+trade(s)",
                status_code=303,
            )

        name = ph.name
        db.delete(ph)
        db.commit()

    return RedirectResponse(url=f"/settings/?msg=MTF+Phase+{quote(name)}+removed", status_code=303)
