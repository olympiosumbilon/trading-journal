from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from services.ai_service import get_ai_insights

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def ai_review(request: Request):
    result = get_ai_insights()
    return templates.TemplateResponse(
        request,
        "ai/review.html",
        {"result": result},
    )
