import os
import re
import mimetypes
from pathlib import Path
from typing import Dict, List, Any, Optional

COURSE_ROOT = os.environ.get("PHOTON_COURSE_PATH", r"D:\Trading\Photon File\Photon -  Zero To Funded 2024")

VIDEO_EXTENSIONS = {".mp4", ".ts", ".mkv", ".mov", ".webm", ".avi", ".m4v"}
DOC_EXTENSIONS = {".docx", ".doc", ".pdf", ".txt", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".url"}


def natural_sort_key(s: str) -> List[Any]:
    """Provides natural alphanumeric sorting for human-readable numbered items (e.g. 1, 2, 10)."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r"(\d+)", s)]


def clean_title(filename: str) -> str:
    """Strips extension and cleans redundant symbols for elegant display."""
    stem = os.path.splitext(filename)[0]
    # Remove leading numbering like '1. ', '01. ' for clean subtitle if needed
    return stem.strip()


def get_file_type(ext: str) -> str:
    ext = ext.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in {".pdf"}:
        return "pdf"
    if ext in {".docx", ".doc"}:
        return "word"
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        return "image"
    if ext in {".xlsx", ".xls"}:
        return "excel"
    if ext in {".url"}:
        return "link"
    return "document"


def detect_video_container(file_path: str) -> str:
    """Detects whether video is native MP4 (ftyp) or MPEG-TS (0x47 sync byte)."""
    try:
        with open(file_path, "rb") as f:
            h = f.read(16)
            if len(h) >= 4 and h[0] == 0x47:
                return "ts"
            if b"ftyp" in h:
                return "mp4"
    except Exception:
        pass
    return "mp4"


def scan_directory_tree(dir_path: str, base_root: str) -> Dict[str, Any]:
    """Recursively scans a directory and structures subdirectories, videos, and documents."""
    if not os.path.exists(dir_path):
        return {"name": os.path.basename(dir_path), "rel_path": "", "subdirs": [], "videos": [], "docs": [], "total_videos": 0}

    items = sorted(os.listdir(dir_path), key=natural_sort_key)
    
    subdirs = []
    videos = []
    docs = []
    total_videos = 0

    for item in items:
        full_path = os.path.join(dir_path, item)
        rel_path = os.path.relpath(full_path, base_root).replace("\\", "/")

        if os.path.isdir(full_path):
            sub_res = scan_directory_tree(full_path, base_root)
            if sub_res["videos"] or sub_res["subdirs"] or sub_res["docs"]:
                subdirs.append(sub_res)
                total_videos += sub_res["total_videos"]
        elif os.path.isfile(full_path):
            ext = os.path.splitext(item)[1].lower()
            file_size = os.path.getsize(full_path)
            file_size_mb = round(file_size / (1024 * 1024), 1)

            if ext in VIDEO_EXTENSIONS:
                container = detect_video_container(full_path)
                videos.append({
                    "name": item,
                    "title": clean_title(item),
                    "rel_path": rel_path,
                    "full_path": full_path,
                    "ext": ext,
                    "type": "video",
                    "container": container,
                    "size_mb": file_size_mb,
                })
                total_videos += 1
            elif ext in DOC_EXTENSIONS:
                docs.append({
                    "name": item,
                    "title": clean_title(item),
                    "rel_path": rel_path,
                    "full_path": full_path,
                    "ext": ext,
                    "type": get_file_type(ext),
                    "size_mb": file_size_mb,
                })

    return {
        "name": os.path.basename(dir_path),
        "rel_path": os.path.relpath(dir_path, base_root).replace("\\", "/"),
        "subdirs": subdirs,
        "videos": videos,
        "docs": docs,
        "total_videos": total_videos,
        "total_docs": len(docs),
    }


def get_course_structure() -> List[Dict[str, Any]]:
    """Returns top-level modules and their full nested structure."""
    if not os.path.exists(COURSE_ROOT):
        return []

    modules = []
    for item in sorted(os.listdir(COURSE_ROOT), key=natural_sort_key):
        item_path = os.path.join(COURSE_ROOT, item)
        if os.path.isdir(item_path):
            tree = scan_directory_tree(item_path, COURSE_ROOT)
            modules.append(tree)

    return modules


def flatten_all_lessons(modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flattens all video lessons into a sequential ordered playlist for Next/Prev navigation."""
    flat = []

    def _traverse(node: Dict[str, Any], module_name: str, section_path: str):
        current_section = f"{section_path} > {node['name']}" if section_path else node['name']
        for vid in node.get("videos", []):
            flat.append({
                **vid,
                "module_name": module_name,
                "section_name": current_section,
                "folder_docs": node.get("docs", []),
            })
        for sub in node.get("subdirs", []):
            _traverse(sub, module_name, current_section)

    for m in modules:
        _traverse(m, m["name"], "")

    return flat


def find_lesson_by_path(rel_path: str) -> Optional[Dict[str, Any]]:
    """Finds a specific lesson by its relative path, along with adjacent previous and next lessons."""
    modules = get_course_structure()
    playlist = flatten_all_lessons(modules)

    normalized_target = rel_path.replace("\\", "/").strip("/")

    for idx, item in enumerate(playlist):
        if item["rel_path"].replace("\\", "/").strip("/") == normalized_target:
            prev_lesson = playlist[idx - 1] if idx > 0 else None
            next_lesson = playlist[idx + 1] if idx < len(playlist) - 1 else None
            return {
                "lesson": item,
                "prev_lesson": prev_lesson,
                "next_lesson": next_lesson,
                "playlist_index": idx + 1,
                "playlist_total": len(playlist),
            }

    return None


def search_course(query: str) -> List[Dict[str, Any]]:
    """Searches through all lessons and materials by keyword."""
    if not query:
        return []
    
    q = query.lower().strip()
    modules = get_course_structure()
    playlist = flatten_all_lessons(modules)

    results = []
    for item in playlist:
        if q in item["title"].lower() or q in item["module_name"].lower() or q in item["section_name"].lower():
            results.append(item)

    return results
