import os
import re
import urllib.parse
import mimetypes
from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database import SessionLocal
from models import CourseProgress, CourseNote
from services.course_service import (
    COURSE_ROOT,
    get_course_structure,
    flatten_all_lessons,
    find_lesson_by_path,
    search_course,
)

router = APIRouter(prefix="/course", tags=["Photon Course"])
templates = Jinja2Templates(directory="templates")


class ProgressPayload(BaseModel):
    lesson_path: str
    is_completed: bool
    last_position_seconds: Optional[float] = 0.0


class NotePayload(BaseModel):
    lesson_path: str
    content: str


@router.get("/")
def course_index(request: Request, q: str = ""):
    """Main Photon Academy Hub showing all modules, video counts, and quick jump-in lessons."""
    modules = get_course_structure()
    playlist = flatten_all_lessons(modules)
    search_results = search_course(q) if q else []

    total_videos = len(playlist)
    first_lesson = playlist[0] if playlist else None

    db = SessionLocal()
    try:
        completed_rows = db.query(CourseProgress).filter(CourseProgress.is_completed == True).all()
        completed_set = {r.lesson_path for r in completed_rows}
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "course/index.html",
        {
            "modules": modules,
            "total_videos": total_videos,
            "first_lesson": first_lesson,
            "search_query": q,
            "search_results": search_results,
            "course_root": COURSE_ROOT,
            "completed_lessons": list(completed_set),
            "completed_count": len(completed_set),
        },
    )


@router.get("/watch")
def watch_lesson(request: Request, file: str = ""):
    """Dedicated video player view with module lesson navigation, notes pad, and resources."""
    modules = get_course_structure()
    playlist = flatten_all_lessons(modules)

    if not playlist:
        return RedirectResponse(url="/course/")

    if not file:
        file = playlist[0]["rel_path"]

    found = find_lesson_by_path(file)
    if not found:
        # Fallback to first lesson if not found
        found = {
            "lesson": playlist[0],
            "prev_lesson": None,
            "next_lesson": playlist[1] if len(playlist) > 1 else None,
            "playlist_index": 1,
            "playlist_total": len(playlist),
        }

    db = SessionLocal()
    try:
        completed_rows = db.query(CourseProgress).filter(CourseProgress.is_completed == True).all()
        completed_lessons = [r.lesson_path for r in completed_rows]

        # Load note for current lesson
        note_row = db.query(CourseNote).filter(CourseNote.lesson_path == file).first()
        lesson_note = note_row.content if note_row and note_row.content else ""
    finally:
        db.close()

    return templates.TemplateResponse(
        request,
        "course/watch.html",
        {
            "modules": modules,
            "current_lesson": found["lesson"],
            "prev_lesson": found["prev_lesson"],
            "next_lesson": found["next_lesson"],
            "playlist_index": found["playlist_index"],
            "playlist_total": found["playlist_total"],
            "playlist": playlist,
            "course_root": COURSE_ROOT,
            "completed_lessons": completed_lessons,
            "lesson_note": lesson_note,
        },
    )


@router.get("/api/progress")
def get_course_progress():
    """Returns list of completed lesson paths from server database."""
    db = SessionLocal()
    try:
        rows = db.query(CourseProgress).filter(CourseProgress.is_completed == True).all()
        return {
            "status": "ok",
            "completed_lessons": [r.lesson_path for r in rows],
            "total_completed": len(rows),
        }
    finally:
        db.close()


@router.post("/api/progress")
def update_course_progress(payload: ProgressPayload):
    """Synchronizes lesson completion status directly with SQLite backend for all network/Tailscale devices."""
    db = SessionLocal()
    try:
        progress = db.query(CourseProgress).filter(CourseProgress.lesson_path == payload.lesson_path).first()
        if not progress:
            progress = CourseProgress(
                lesson_path=payload.lesson_path,
                is_completed=payload.is_completed,
                last_position_seconds=payload.last_position_seconds or 0.0,
                completed_at=datetime.utcnow() if payload.is_completed else None,
            )
            db.add(progress)
        else:
            progress.is_completed = payload.is_completed
            progress.last_position_seconds = payload.last_position_seconds or 0.0
            if payload.is_completed and not progress.completed_at:
                progress.completed_at = datetime.utcnow()
            elif not payload.is_completed:
                progress.completed_at = None
        db.commit()
        return {"status": "ok", "lesson_path": payload.lesson_path, "is_completed": payload.is_completed}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/api/notes")
def get_lesson_note(path: str = Query(...)):
    """Retrieves server-synchronized personal notes for a lesson."""
    db = SessionLocal()
    try:
        note = db.query(CourseNote).filter(CourseNote.lesson_path == path).first()
        return {"status": "ok", "lesson_path": path, "content": note.content if note else ""}
    finally:
        db.close()


@router.post("/api/notes")
def save_lesson_note(payload: NotePayload):
    """Persists personal lesson notes to SQLite backend across all devices."""
    db = SessionLocal()
    try:
        note = db.query(CourseNote).filter(CourseNote.lesson_path == payload.lesson_path).first()
        if not note:
            note = CourseNote(lesson_path=payload.lesson_path, content=payload.content)
            db.add(note)
        else:
            note.content = payload.content
        db.commit()
        return {"status": "ok", "lesson_path": payload.lesson_path}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()



@router.get("/stream")
def stream_video(request: Request, path: str):
    """High-performance range streaming endpoint for instant seeking in course videos."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    # Security check: Ensure path is within COURSE_ROOT
    if not full_path.startswith(os.path.normpath(COURSE_ROOT)):
        raise HTTPException(status_code=403, detail="Forbidden file access")

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Video file not found")

    file_size = os.path.getsize(full_path)
    range_header = request.headers.get("range", "")

    start = 0
    end = file_size - 1

    if range_header:
        match = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if match:
            start = int(match.group(1))
            if match.group(2):
                end = int(match.group(2))

    length = end - start + 1

    def iter_chunks():
        with open(full_path, "rb") as f:
            f.seek(start)
            bytes_left = length
            chunk_size = 1024 * 1024  # 1MB chunks
            while bytes_left > 0:
                read_size = min(chunk_size, bytes_left)
                data = f.read(read_size)
                if not data:
                    break
                bytes_left -= len(data)
                yield data

    ext = os.path.splitext(full_path)[1].lower()
    mime_type = mimetypes.guess_type(full_path)[0] or "video/mp4"
    if ext == ".ts":
        mime_type = "video/mp2t"
    elif ext == ".mkv":
        mime_type = "video/x-matroska"

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Type": mime_type,
    }

    return StreamingResponse(iter_chunks(), status_code=206, headers=headers)


@router.get("/file")
def view_course_file(path: str):
    """Direct inline file viewing endpoint. Automatically redirects .url files to target destination."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    if not full_path.startswith(os.path.normpath(COURSE_ROOT)):
        raise HTTPException(status_code=403, detail="Forbidden file access")

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    ext = os.path.splitext(full_path)[1].lower()
    
    # If .url internet shortcut, redirect to target URL
    if ext == ".url":
        from services.course_service import read_url_shortcut
        target_url = read_url_shortcut(full_path)
        if target_url:
            return RedirectResponse(url=target_url)

    mime_type, _ = mimetypes.guess_type(full_path)
    if not mime_type:
        mime_type = "application/octet-stream"

    filename = os.path.basename(full_path)
    headers = {
        "Content-Disposition": f'inline; filename="{filename}"'
    }
    return FileResponse(full_path, media_type=mime_type, headers=headers)


@router.get("/doc")
def view_document_page(request: Request, path: str):
    """Clean, dedicated document reader for course docs and notes without downloads."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    if not full_path.startswith(os.path.normpath(COURSE_ROOT)) or not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Document not found")

    ext = os.path.splitext(full_path)[1].lower()
    filename = os.path.basename(full_path)
    title = os.path.splitext(filename)[0]

    from services.course_service import read_docx_paragraphs, read_url_shortcut

    if ext in [".docx", ".doc"]:
        paragraphs = read_docx_paragraphs(full_path)
    elif ext in [".txt", ".md"]:
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            paragraphs = [{"text": line.strip(), "is_heading": False} for line in lines if line.strip()]
        except Exception:
            paragraphs = []
    elif ext == ".url":
        url = read_url_shortcut(full_path)
        if url:
            return RedirectResponse(url=url)
        paragraphs = []
    else:
        return RedirectResponse(url=f"/course/file?path={urllib.parse.quote(decoded_path)}")

    return templates.TemplateResponse(
        request,
        "course/doc_view.html",
        {
            "title": title,
            "filename": filename,
            "paragraphs": paragraphs,
            "rel_path": decoded_path,
        },
    )


@router.get("/read-doc")
def read_doc_endpoint(path: str):
    """Parses .docx or text document and returns structured JSON for in-app reader modal."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    if not full_path.startswith(os.path.normpath(COURSE_ROOT)) or not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="Document not found")

    ext = os.path.splitext(full_path)[1].lower()
    filename = os.path.basename(full_path)
    title = os.path.splitext(filename)[0]

    from services.course_service import read_docx_paragraphs, read_url_shortcut

    if ext in [".docx", ".doc"]:
        paragraphs = read_docx_paragraphs(full_path)
        return {
            "status": "ok",
            "type": "docx",
            "title": title,
            "filename": filename,
            "paragraphs": paragraphs,
            "rel_path": decoded_path,
        }
    elif ext == ".url":
        url = read_url_shortcut(full_path)
        return {
            "status": "ok",
            "type": "url",
            "title": title,
            "filename": filename,
            "url": url,
            "rel_path": decoded_path,
        }
    elif ext in [".txt", ".md"]:
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            paragraphs = [{"text": line.strip(), "is_heading": False} for line in lines if line.strip()]
            return {
                "status": "ok",
                "type": "text",
                "title": title,
                "filename": filename,
                "paragraphs": paragraphs,
                "rel_path": decoded_path,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "ok",
        "type": "other",
        "title": title,
        "filename": filename,
        "rel_path": decoded_path,
    }


@router.post("/open-desktop")
def open_desktop_file(request: Request, path: str = Query(...)):
    """Launches the file in its default desktop application on the host machine without downloading."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    if not full_path.startswith(os.path.normpath(COURSE_ROOT)) or not os.path.exists(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    from services.course_service import open_file_in_desktop
    success = open_file_in_desktop(full_path)
    return {"status": "ok" if success else "error"}
