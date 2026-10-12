import json
import os


class BookingStore:
    """Bookings in one JSON file, written atomically. Fine for one salon; not for thousands of users."""

    def __init__(self, path):
        self.path = path
        self.items = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.items = json.load(f)

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.items, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def active(self):
        return [b for b in self.items if b["status"] == "active"]

    def taken(self):
        return {b["start"] for b in self.active()}

    def add(self, chat_id, name, phone, start):
        """start: ISO string. Raises ValueError if the slot is already taken (checked here, at write time)."""
        if start in self.taken():
            raise ValueError("slot taken")
        bid = max([b["id"] for b in self.items] + [0]) + 1
        b = {"id": bid, "chat_id": chat_id, "name": name, "phone": phone, "start": start, "status": "active", "reminded": False}
        self.items.append(b)
        self._save()
        return b

    def of_chat(self, chat_id):
        return sorted((b for b in self.active() if b["chat_id"] == chat_id), key=lambda b: b["start"])

    def cancel(self, chat_id, bid):
        for b in self.items:
            if b["id"] == bid and b["chat_id"] == chat_id and b["status"] == "active":
                b["status"] = "cancelled"
                self._save()
                return b
        return None

    def mark_reminded(self, bid):
        for b in self.items:
            if b["id"] == bid:
                b["reminded"] = True
        self._save()
