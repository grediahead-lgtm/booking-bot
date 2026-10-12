import argparse
import datetime as dt
import json
import os
import sys
import time

from .core import BookingBot
from .slots import due_reminders
from .store import BookingStore
from .telegram_api import TelegramClient

NEED = ["greeting", "stopped", "too_many", "no_slots", "pick_day", "pick_slot", "bad_choice", "ask_name", "bad_name",
        "ask_phone", "bad_phone", "slot_taken", "booked", "no_bookings", "how_cancel", "cancelled", "not_found", "reminder"]


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    for k in ("work_days", "start", "end", "slot_minutes", "days_ahead"):
        if k not in cfg:
            raise ValueError("config is missing %r" % k)
    miss = [k for k in NEED if not cfg.get("texts", {}).get(k)]
    if miss:
        raise ValueError("config.texts is missing: " + ", ".join(miss))
    if not 5 <= cfg["slot_minutes"] <= 480:
        raise ValueError("slot_minutes must be between 5 and 480")
    return cfg


def main(argv=None):
    ap = argparse.ArgumentParser(prog="booking_bot")
    ap.add_argument("--config", required=True)
    ap.add_argument("--data", default="bookings.json")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    cfg = load_config(args.config)
    store = BookingStore(args.data)
    if args.check:
        print("config ok, active bookings:", len(store.active()))
        return 0
    client = TelegramClient(os.environ.get("TELEGRAM_BOT_TOKEN", ""))
    owner = cfg.get("owner_chat_id")
    notify = (lambda b: client.send(owner, "New booking #%d: %s, %s, %s" % (b["id"], b["name"], b["phone"], b["start"]))) if owner else None
    bot = BookingBot(cfg, store, notify_owner=notify)
    offset, last_check = 0, 0.0
    while True:
        try:
            for upd in client.updates(offset):
                offset = upd["update_id"] + 1
                m = upd.get("message") or {}
                if m.get("chat", {}).get("type") != "private" or m.get("from", {}).get("is_bot") or not m.get("text"):
                    continue
                for r in bot.handle(m["chat"]["id"], m["text"]):
                    client.send(m["chat"]["id"], r)
            if time.time() - last_check > 300:
                last_check = time.time()
                for b in due_reminders(store.active(), dt.datetime.now(), cfg.get("reminder_hours", 24)):
                    client.send(b["chat_id"], cfg["texts"]["reminder"].format(start=b["start"].replace("T", " ")))
                    store.mark_reminded(b["id"])
        except KeyboardInterrupt:
            return 0
        except Exception as e:
            print("error:", type(e).__name__, file=sys.stderr)
            time.sleep(5)


if __name__ == "__main__":
    sys.exit(main())
