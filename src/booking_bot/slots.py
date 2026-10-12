import datetime as dt


def _t(s):
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def day_slots(day, cfg):
    """All slot start datetimes of one day by the working hours; none on days off."""
    if day.weekday() not in cfg["work_days"]:
        return []
    cur = dt.datetime.combine(day, _t(cfg["start"]))
    end = dt.datetime.combine(day, _t(cfg["end"]))
    step = dt.timedelta(minutes=cfg["slot_minutes"])
    out = []
    while cur + step <= end:
        out.append(cur)
        cur += step
    return out


def free_slots(day, cfg, taken, now):
    """Free slots of a day: not taken, and at least `min_notice_minutes` from now."""
    limit = now + dt.timedelta(minutes=cfg.get("min_notice_minutes", 60))
    return [s for s in day_slots(day, cfg) if s.isoformat(timespec="minutes") not in taken and s >= limit]


def days_with_free(cfg, taken, now):
    out = []
    for i in range(cfg["days_ahead"] + 1):
        d = now.date() + dt.timedelta(days=i)
        if free_slots(d, cfg, taken, now):
            out.append(d)
    return out


def due_reminders(bookings, now, hours_before):
    """Active bookings starting within the window that were not reminded yet and are in the future."""
    limit = now + dt.timedelta(hours=hours_before)
    res = []
    for b in bookings:
        start = dt.datetime.fromisoformat(b["start"])
        if b["status"] == "active" and not b["reminded"] and now < start <= limit:
            res.append(b)
    return res
