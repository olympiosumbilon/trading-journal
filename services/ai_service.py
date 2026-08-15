import requests
import json
from config import settings
from database import SessionLocal
from models import Trade, Session, Instrument, Strategy
from sqlalchemy import func

OLLAMA_URL = settings.OLLAMA_BASE_URL
MODEL = settings.OLLAMA_MODEL


def _summarize_trades() -> dict:
    """Gather trade statistics for the AI prompt."""
    with SessionLocal() as db:
        total = db.query(Trade).count()
        wins = db.query(Trade).filter(Trade.is_win == True).count()
        losses = db.query(Trade).filter(Trade.is_loss == True).count()

        total_r = db.query(func.sum(Trade.fixed_r_target)).scalar() or 0.0
        avg_r = db.query(func.avg(Trade.fixed_r_target)).scalar() or 0.0
        peak_r = db.query(func.max(Trade.peak_r)).scalar() or 0.0
        max_dd = db.query(func.min(Trade.max_drawdown)).scalar() or 0.0

        # Per-instrument stats
        inst_stats = (
            db.query(
                Instrument.name,
                func.count(Trade.id),
                func.sum(Trade.fixed_r_target),
                func.avg(Trade.fixed_r_target),
            )
            .join(Trade.instrument_obj)
            .group_by(Instrument.name)
            .all()
        )

        # Per-session stats
        sess_stats = (
            db.query(
                Session.name,
                func.count(Trade.id),
                func.sum(Trade.fixed_r_target),
                func.avg(Trade.fixed_r_target),
            )
            .join(Trade.session_obj)
            .group_by(Session.name)
            .all()
        )

        # Per-setup stats
        setup_stats = (
            db.query(
                Strategy.name,
                func.count(Trade.id),
                func.sum(Trade.fixed_r_target),
                func.avg(Trade.fixed_r_target),
            )
            .join(Trade.strategy_obj)
            .group_by(Strategy.name)
            .all()
        )

        # Recent streaks
        recent = (
            db.query(Trade)
            .order_by(Trade.id.desc())
            .limit(10)
            .all()
        )
        recent_results = []
        for t in recent:
            recent_results.append({
                "date": str(t.entry_date),
                "instrument": t.instrument_obj.name if t.instrument_obj else "",
                "setup": t.strategy_obj.name if t.strategy_obj else "",
                "session": t.session_obj.name if t.session_obj else "",
                "result": "Win" if t.is_win else ("Loss" if t.is_loss else "Unknown"),
                "r": round(t.fixed_r_target or 0.0, 2),
            })

    return {
        "total_trades": total,
        "wins": wins,
        "losses": losses,
        "win_rate": round(wins / total * 100, 1) if total else 0,
        "total_r": round(float(total_r), 2),
        "avg_r": round(float(avg_r), 2),
        "peak_r": round(float(peak_r), 2),
        "max_drawdown": round(float(max_dd), 2),
        "per_instrument": [
            {
                "name": i[0],
                "trades": i[1],
                "total_r": round(float(i[2] or 0), 2),
                "avg_r": round(float(i[3] or 0), 2),
            }
            for i in inst_stats
        ],
        "per_session": [
            {
                "name": s[0],
                "trades": s[1],
                "total_r": round(float(s[2] or 0), 2),
                "avg_r": round(float(s[3] or 0), 2),
            }
            for s in sess_stats
        ],
        "per_setup": [
            {
                "name": s[0],
                "trades": s[1],
                "total_r": round(float(s[2] or 0), 2),
                "avg_r": round(float(s[3] or 0), 2),
            }
            for s in setup_stats
        ],
        "recent_10": list(reversed(recent_results)),
    }


def _build_prompt(stats: dict) -> str:
    prompt = f"""You are a trading performance analyst. Analyze the following trade statistics and provide actionable insights in 4 sections:

1. SETUP & STRATEGY — Which setups are working best? Which are underperforming?
2. SESSION & TIMING — Which sessions or time periods show strongest edge?
3. RISK & PSYCHOLOGY — Are there tilt patterns (revenge trading, overtrading after losses)? Is the trader adhering to their planned R targets?
4. TOP 3 ACTIONS — Concrete, prioritized recommendations to improve performance.

Keep insights concise, data-backed, and directly tied to the numbers. Do not make up facts not in the data.

--- TRADE STATISTICS ---
Total trades: {stats['total_trades']}
Wins: {stats['wins']} | Losses: {stats['losses']} | Win rate: {stats['win_rate']}%
Total R: {stats['total_r']} | Avg R/trade: {stats['avg_r']}
Peak R: {stats['peak_r']} | Max drawdown: {stats['max_drawdown']}

Per instrument:
"""
    for i in stats["per_instrument"]:
        prompt += f"  {i['name']}: {i['trades']} trades, Total R {i['total_r']}, Avg R {i['avg_r']}\n"

    prompt += "\nPer session:\n"
    for s in stats["per_session"]:
        prompt += f"  {s['name']}: {s['trades']} trades, Total R {s['total_r']}, Avg R {s['avg_r']}\n"

    prompt += "\nPer setup:\n"
    for s in stats["per_setup"]:
        prompt += f"  {s['name']}: {s['trades']} trades, Total R {s['total_r']}, Avg R {s['avg_r']}\n"

    prompt += "\nRecent 10 trades (oldest to newest):\n"
    for t in stats["recent_10"]:
        prompt += f"  {t['date']} | {t['instrument']} | {t['setup']} | {t['session']} | {t['result']} | R {t['r']}\n"

    prompt += "\n--- YOUR ANALYSIS ---\n"
    return prompt


def get_ai_insights() -> dict:
    """Call Ollama and return parsed insights."""
    stats = _summarize_trades()
    prompt = _build_prompt(stats)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 800,
                },
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("response", "")
    except Exception as e:
        return {
            "error": str(e),
            "raw": "",
            "stats": stats,
        }

    # Simple section extraction
    sections = {
        "setup": "",
        "session": "",
        "risk": "",
        "actions": "",
    }
    current = None
    for line in text.splitlines():
        lower = line.lower()
        if "setup" in lower and "strategy" in lower:
            current = "setup"
            continue
        if "session" in lower and "timing" in lower:
            current = "session"
            continue
        if "risk" in lower and "psychology" in lower:
            current = "risk"
            continue
        if "top 3" in lower or "actions" in lower:
            current = "actions"
            continue
        if current:
            sections[current] += line + "\n"

    return {
        "error": None,
        "raw": text,
        "sections": {k: v.strip() for k, v in sections.items()},
        "stats": stats,
    }
