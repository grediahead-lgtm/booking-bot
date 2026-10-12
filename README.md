# booking-bot

A Telegram bot where customers book appointment slots (salon, masseur, tutor, repair): it shows the free days and times, takes name and phone, confirms, lets the customer cancel, and reminds them the day before. Python standard library only.

## What it does
- `/book`: choose a day (numbered list of days that still have free slots), a time, then name and phone. `/my` lists your bookings, `/unbook N` cancels one, `/cancel` stops the dialog.
- Working days, hours, slot length, how many days ahead and the minimum notice (default 60 minutes) are set in the config.
- **No double booking:** the slot is checked again at the moment of saving, so if two customers choose the same time, the second gets "this time was just taken". A customer can cancel only their own bookings, and has at most 3 active bookings.
- Cancelled slots become free again. The owner can get a message for every new booking (`owner_chat_id`). Reminders go out once, `reminder_hours` before the start.
- Data is one JSON file (`bookings.json`, written atomically). Private chats only, rate limit per chat, token from `TELEGRAM_BOT_TOKEN` only, texts and phones are not logged.

## Quick start
```bash
cp examples/config.example.json config.json       # change hours and texts
PYTHONPATH=src python3 -m booking_bot --config config.json --check
TELEGRAM_BOT_TOKEN=123456:your-token PYTHONPATH=src python3 -m booking_bot --config config.json
```
Tests: `python3 -m unittest discover -s tests` (no internet, no real token).

## Limits (read this)
- One master / one calendar, one slot length, no breaks or holidays yet (days off are only by weekday). Times are local time of the machine where the bot runs; there is no time-zone handling.
- Dialog state is in memory: a restart cancels unfinished dialogs (saved bookings stay).
- The reminder loop and the Telegram calls are not covered by an automated test against Telegram itself; the booking logic, slots, reminders selection and storage are. Try it with your own test bot first.
- A JSON file is fine for one small business, not for thousands of bookings.

MIT license.

---

# booking-bot (українською)

Telegram-бот для запису на прийом (салон, масаж, репетитор, ремонт): показує вільні дні й години, бере ім'я та телефон, підтверджує, дозволяє скасувати й нагадує напередодні. Лише стандартна бібліотека Python.

**Запуск:** `cp examples/config.example.json config.json`, `--check`, потім з `TELEGRAM_BOT_TOKEN`. Подвійний запис на той самий час неможливий: слот перевіряється повторно в момент збереження.

**Важливо:** один майстер і один календар, без перерв і свят, без часових поясів; цикл нагадувань і виклики Telegram автоматично проти Telegram не тестувалися.
