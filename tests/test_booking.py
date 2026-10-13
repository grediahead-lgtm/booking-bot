import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

from booking_bot.__main__ import load_config  # noqa: E402
from booking_bot.core import BookingBot  # noqa: E402
from booking_bot.slots import day_slots, due_reminders, free_slots  # noqa: E402
from booking_bot.store import BookingStore  # noqa: E402

CFG = load_config(os.path.join(ROOT, "examples", "config.example.json"))
MON = dt.datetime(2026, 10, 12, 9, 0)  # a Monday, 09:00


def new_bot(d, now=MON, **kw):
    store = BookingStore(os.path.join(d, "b.json"))
    return BookingBot(CFG, store, now=lambda: now, **kw), store


def say(bot, chat, *msgs):
    out = []
    for m in msgs:
        out += bot.handle(chat, m)
    return out


class SlotTests(unittest.TestCase):
    def test_day_slots(self):
        s = day_slots(MON.date(), CFG)
        self.assertEqual([x.strftime("%H:%M") for x in s], ["10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"])

    def test_weekend_has_none(self):
        self.assertEqual(day_slots(dt.date(2026, 10, 17), CFG), [])  # Saturday

    def test_taken_and_notice(self):
        now = dt.datetime(2026, 10, 12, 10, 30)
        taken = {"2026-10-12T12:00"}
        got = [x.strftime("%H:%M") for x in free_slots(now.date(), CFG, taken, now)]
        self.assertNotIn("12:00", got)
        self.assertNotIn("10:00", got)
        self.assertNotIn("11:00", got)  # inside the 60-minute notice window
        self.assertIn("13:00", got)

    def test_reminders(self):
        now = dt.datetime(2026, 10, 12, 9, 0)
        mk = lambda i, start, **kw: dict({"id": i, "start": start, "status": "active", "reminded": False}, **kw)
        bs = [mk(1, "2026-10-13T08:00"), mk(2, "2026-10-13T10:00"), mk(3, "2026-10-12T08:00"),
              mk(4, "2026-10-13T08:00", reminded=True), mk(5, "2026-10-13T08:00", status="cancelled")]
        self.assertEqual([b["id"] for b in due_reminders(bs, now, 24)], [1])


class FlowTests(unittest.TestCase):
    def test_full_booking(self):
        with tempfile.TemporaryDirectory() as d:
            seen = []
            bot, store = new_bot(d, notify_owner=seen.append)
            out = say(bot, 1, "/book", "1", "2", "Ira", "+380501112233")
            self.assertIn("Booked #1", out[-1])
            self.assertEqual(len(store.active()), 1)
            self.assertEqual(seen[0]["name"], "Ira")

    def test_same_slot_cannot_be_booked_twice(self):
        with tempfile.TemporaryDirectory() as d:
            bot, store = new_bot(d)
            say(bot, 1, "/book", "1", "1", "Ira", "380501112233")
            # chat 2 saw the same list before chat 1 finished, so it picks the same slot
            say(bot, 2, "/book", "1", "1", "Oleg")
            store.add(9, "x", "380500000000", bot.sessions[2]["start"])  # slot gets taken by someone else
            out = say(bot, 2, "380509998877")
            self.assertEqual(out[-1], CFG["texts"]["slot_taken"])
            self.assertEqual(len(store.active()), 2)

    def test_validation_keeps_the_step(self):
        with tempfile.TemporaryDirectory() as d:
            bot, _ = new_bot(d)
            out = say(bot, 1, "/book", "99", "abc")
            self.assertEqual(out[-2:], [CFG["texts"]["bad_choice"]] * 2)
            say(bot, 1, "1", "1")
            self.assertEqual(say(bot, 1, "I")[-1], CFG["texts"]["bad_name"])
            say(bot, 1, "Ira")
            self.assertEqual(say(bot, 1, "12345")[-1], CFG["texts"]["bad_phone"])

    def test_limit_my_unbook(self):
        with tempfile.TemporaryDirectory() as d:
            bot, store = new_bot(d)
            for k in range(3):
                say(bot, 1, "/book", "1", "1", "Ira", "380501112233")
            self.assertIn("already have 3", say(bot, 1, "/book")[0])
            self.assertIn("#1", say(bot, 1, "/my")[0])
            self.assertEqual(say(bot, 2, "/unbook 1")[0], CFG["texts"]["not_found"])  # not someone else's booking
            self.assertIn("cancelled", say(bot, 1, "/unbook 1")[0])
            self.assertEqual(len(store.of_chat(1)), 2)
            self.assertEqual(say(bot, 1, "/unbook")[0], CFG["texts"]["how_cancel"])

    def test_cancelled_slot_is_free_again(self):
        with tempfile.TemporaryDirectory() as d:
            bot, store = new_bot(d)
            say(bot, 1, "/book", "1", "1", "Ira", "380501112233")
            first = store.active()[0]["start"]
            say(bot, 1, "/unbook 1")
            self.assertNotIn(first, store.taken())

    def test_persistence_and_atomic_file(self):
        with tempfile.TemporaryDirectory() as d:
            bot, store = new_bot(d)
            say(bot, 1, "/book", "1", "1", "Ira", "380501112233")
            again = BookingStore(os.path.join(d, "b.json"))
            self.assertEqual(len(again.active()), 1)
            self.assertFalse(os.path.exists(os.path.join(d, "b.json.tmp")))

    def test_failed_owner_notification_keeps_the_confirmation(self):
        with tempfile.TemporaryDirectory() as d:
            def boom(b):
                raise RuntimeError("telegram down")
            bot, store = new_bot(d, notify_owner=boom)
            out = say(bot, 1, "/book", "1", "1", "Ira", "380501112233")
            self.assertIn("Booked #1", out[-1])
            self.assertEqual(len(store.active()), 1)

    def test_no_session_and_rate_limit(self):
        with tempfile.TemporaryDirectory() as d:
            bot, _ = new_bot(d, rate_limit=2)
            self.assertEqual(bot.handle(1, "hello"), [CFG["texts"]["greeting"]])
            bot.handle(1, "hi")
            self.assertEqual(bot.handle(1, "hi"), [])


class ConfigTests(unittest.TestCase):
    def test_missing_text_and_bad_slot_minutes(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            with open(os.path.join(ROOT, "examples", "config.example.json"), encoding="utf-8") as f:
                good = json.load(f)
            for change in ({"texts": {"greeting": "x"}}, {"slot_minutes": 1}):
                bad = dict(good, **change)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(bad, f)
                with self.assertRaises(ValueError, msg=str(change)):
                    load_config(p)


if __name__ == "__main__":
    unittest.main()
