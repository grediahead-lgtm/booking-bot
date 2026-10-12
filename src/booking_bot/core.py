import datetime as dt
import re
import time

from .slots import days_with_free, free_slots

MAX_ACTIVE = 3


def clean(s, n=80):
    return re.sub(r"\s+", " ", s or "").strip()[:n]


class BookingBot:
    def __init__(self, cfg, store, now=None, notify_owner=None, rate_limit=20):
        self.cfg, self.store, self.notify_owner = cfg, store, notify_owner
        self.now = now or dt.datetime.now
        self.sessions, self._hits, self.rate_limit = {}, {}, rate_limit

    def _limited(self, chat):
        t = time.monotonic()
        h = [x for x in self._hits.get(chat, []) if t - x < 60] + [t]
        self._hits[chat] = h
        return len(h) > self.rate_limit

    def handle(self, chat, text):
        if self._limited(chat):
            return []
        t, text = self.cfg["texts"], clean(text, 200)
        cmd = text.split(" ")[0].lower() if text.startswith("/") else ""
        if cmd in ("/start", "/help"):
            return [t["greeting"]]
        if cmd == "/cancel":
            self.sessions.pop(chat, None)
            return [t["stopped"]]
        if cmd == "/my":
            return [self._mine(chat)]
        if cmd == "/unbook":
            return [self._unbook(chat, text)]
        if cmd == "/book":
            return self._start(chat)
        s = self.sessions.get(chat)
        if not s:
            return [t["greeting"]]
        return getattr(self, "_" + s["step"])(chat, s, text)

    def _start(self, chat):
        t = self.cfg["texts"]
        if len(self.store.of_chat(chat)) >= MAX_ACTIVE:
            return [t["too_many"].format(n=MAX_ACTIVE)]
        days = days_with_free(self.cfg, self.store.taken(), self.now())
        if not days:
            return [t["no_slots"]]
        self.sessions[chat] = {"step": "pick_day", "days": days}
        return [t["pick_day"] + "\n" + "\n".join("%d. %s" % (i + 1, d.strftime("%a %d.%m")) for i, d in enumerate(days))]

    @staticmethod
    def _index(text, n):
        return int(text) - 1 if re.fullmatch(r"\d{1,2}", text) and 1 <= int(text) <= n else None

    def _pick_day(self, chat, s, text):
        i = self._index(text, len(s["days"]))
        if i is None:
            return [self.cfg["texts"]["bad_choice"]]
        slots = free_slots(s["days"][i], self.cfg, self.store.taken(), self.now())
        if not slots:  # taken while the customer was choosing
            return self._start(chat)
        s.update(step="pick_slot", slots=slots)
        return [self.cfg["texts"]["pick_slot"] + "\n" + "\n".join("%d. %s" % (k + 1, x.strftime("%H:%M")) for k, x in enumerate(slots))]

    def _pick_slot(self, chat, s, text):
        i = self._index(text, len(s["slots"]))
        if i is None:
            return [self.cfg["texts"]["bad_choice"]]
        s.update(step="name", start=s["slots"][i].isoformat(timespec="minutes"))
        return [self.cfg["texts"]["ask_name"]]

    def _name(self, chat, s, text):
        if len(text) < 2 or text.startswith("/"):
            return [self.cfg["texts"]["bad_name"]]
        s.update(step="phone", name=text)
        return [self.cfg["texts"]["ask_phone"]]

    def _phone(self, chat, s, text):
        digits = re.sub(r"\D", "", text)
        if not 9 <= len(digits) <= 15:
            return [self.cfg["texts"]["bad_phone"]]
        t = self.cfg["texts"]
        try:
            b = self.store.add(chat, s["name"], text, s["start"])
        except ValueError:
            self.sessions.pop(chat, None)
            return [t["slot_taken"]]
        self.sessions.pop(chat, None)
        if self.notify_owner:
            self.notify_owner(b)
        return [t["booked"].format(start=b["start"].replace("T", " "), id=b["id"])]

    def _mine(self, chat):
        items = self.store.of_chat(chat)
        if not items:
            return self.cfg["texts"]["no_bookings"]
        return "\n".join("#%d  %s" % (b["id"], b["start"].replace("T", " ")) for b in items) + "\n" + self.cfg["texts"]["how_cancel"]

    def _unbook(self, chat, text):
        m = re.fullmatch(r"/unbook\s+#?(\d+)", text.lower())
        if not m:
            return self.cfg["texts"]["how_cancel"]
        b = self.store.cancel(chat, int(m.group(1)))
        return self.cfg["texts"]["cancelled"].format(id=b["id"]) if b else self.cfg["texts"]["not_found"]
