import os
import re
import urllib.parse
import mimetypes
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services.course_service import (
    COURSE_ROOT,
    get_course_structure,
    flatten_all_lessons,
    find_lesson_by_path,
    search_course,
)

router = APIRouter(prefix="/course", tags=["Photon Course"])
templates = Jinja2Templates(directory="templates")


@router.get("/")
def course_index(request: Request, q: str = ""):
    """Main Photon Academy Hub showing all modules, video counts, and quick jump-in lessons."""
    modules = get_course_structure()
    playlist = flatten_all_lessons(modules)
    search_results = search_course(q) if q else []

    total_videos = len(playlist)
    first_lesson = playlist[0] if playlist else None

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
        },
    )


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
def download_course_file(path: str):
    """Direct file download / view endpoint for accompanying course docs, PDFs, images."""
    decoded_path = urllib.parse.unquote(path)
    full_path = os.path.normpath(os.path.join(COURSE_ROOT, decoded_path))

    if not full_path.startswith(os.path.normpath(COURSE_ROOT)):
        raise HTTPException(status_code=403, detail="Forbidden file access")

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="File not found")

    filename = os.path.basename(full_path)
    return FileResponse(full_path, filename=filename)
