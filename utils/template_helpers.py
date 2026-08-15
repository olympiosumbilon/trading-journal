from datetime import datetime, time

def format_time_12h(val):
    if not val:
        return "—"
    if hasattr(val, "strftime"):
        # Format as e.g. '10:55 PM' or '8:30 AM'
        res = val.strftime("%I:%M %p")
        return res.lstrip("0") if res.startswith("0") else res
    s = str(val).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M %p", "%I:%M%p"):
        try:
            dt = datetime.strptime(s, fmt)
            res = dt.strftime("%I:%M %p")
            return res.lstrip("0") if res.startswith("0") else res
        except ValueError:
            pass
    return s


def format_duration(minutes):
    if minutes is None:
        return "—"
    try:
        m = int(minutes)
        if m < 0:
            return "—"
        if m < 60:
            return f"{m}m"
        hours = m // 60
        rem_mins = m % 60
        if hours < 24:
            return f"{hours}h {rem_mins}m" if rem_mins > 0 else f"{hours}h"
        days = hours // 24
        rem_hours = hours % 24
        return f"{days}d {rem_hours}h" if rem_hours > 0 else f"{days}d"
    except Exception:
        return str(minutes)

