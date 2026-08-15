from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from services.automation_service import (
    export_trades_csv,
    generate_weekly_report,
    check_alerts,
)
import io

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def automations_index(request: Request):
    alerts = check_alerts()
    return templates.TemplateResponse(
        request,
        "automations/index.html",
        {"alerts": alerts},
    )


@router.get("/export/csv")
def export_csv():
    csv_data = export_trades_csv()
    return StreamingResponse(
        io.StringIO(csv_data),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=trades_export.csv"},
    )


@router.get("/weekly-report")
def weekly_report(request: Request):
    report = generate_weekly_report()
    return templates.TemplateResponse(
        request,
        "automations/weekly_report.html",
        {"report": report},
    )


@router.get("/alerts")
def get_alerts():
    alerts = check_alerts()
    return {"alerts": alerts, "count": len(alerts)}
