# Jayram Dairy Udhyog — v0.5 (feature-complete for Phase 1)

Built per `docs/technical-architecture.md`. This is the first version
covering every module from the original proposal's Phase 1 scope:
Vendor, Production, Orders/Customers, Payments, Login, and Activity
Logging — all working together against one shared local database.

## What's in this version

**Screens (all functional, sidebar navigation):**
- **Dashboard (Home)** — today's milk collected, total vendor payable,
  total customer due, low-stock alert count, recent payments feed
- **Vendor** — vendor CRUD, milk collection with fat-based/flat/override
  pricing, ledger with Paid/Status column, running balance
- **Production** — pooled raw-milk inventory (shared across all
  vendors), product CRUD, batch creation with stock deduction/increment
  and overdraw rejection
- **Orders** — customer CRUD, order creation with stock-aware rejection,
  advance payments linked to orders, running balance
- **Payments** — a single entry point for any vendor or customer
  payment, with a recent-payments feed across both
- **Activity Log** — read-only audit trail of every login and save
  action, with timestamp, app version, username, and action

**Login:** first run shows "create your account"; every run after
shows a real sign-in screen. Passwords are bcrypt-hashed, never stored
in plaintext. Every sign-in and successful save action is written to
a structured local log file.

**Data:** SQLite under `%LOCALAPPDATA%\JayramDairy\` when packaged, or
`_devdata/` when running from source. Schema changes apply via Alembic
on startup. Automatic backups live in `backups\` (before migrations and
once per day on launch; last 10 kept).

## What's NOT in here yet (honestly)

- Nepali BS *input* on date fields — dates display in BS everywhere,
  but entry still uses the system date. Worth a follow-up pass.
- The actual Windows `.exe` — see `BUILD.md`. Build on a real Windows
  machine (PyInstaller + Inno Setup), then smoke-test before the shop PC.
- Code signing / SmartScreen — unsigned builds will show a Windows
  warning; expected until a certificate is purchased.

## Running it yourself

```bash
pip install -r requirements.txt
python app/main.py
```

First launch: create an account (any username/password, 4+ characters).
Subsequent launches: sign in with what you created.

**From source:** seeds 2 vendors, 3 products, 2 customers when the DB is
empty (handy for development).

**Packaged `.exe`:** starts empty — create the account, then add real
vendors, products, and customers. No demo rows.

## Running the tests

```bash
pytest tests/ -v
```

Tests cover pricing, balance, production, orders/stock, payments, auth,
activity logging, dashboard stats, Alembic migrations, backups, and
seed gating.

## Building / upgrading the Windows installer

See `BUILD.md` for:

- Release checklist (bump both version strings, test, PyInstaller, Inno)
- First install and upgrade steps on the shop PC
- How to restore from `%LOCALAPPDATA%\JayramDairy\backups\` if needed

## What to check when you run it

1. Create your account, confirm you land on the Dashboard.
2. Add a milk collection on the Vendor screen — confirm the Dashboard's
   "Milk Collected Today" updates when you go back to Home.
3. Do a Production batch — confirm stock updates, and try over-drawing
   the pool to see the rejection.
4. Place an Order — confirm stock decrements and try over-ordering.
5. Record a standalone Payment — confirm it shows on the Dashboard's
   recent payments and reduces the right balance.
6. Check the Activity Log — every action above should appear there,
   attributed to your username.
7. Confirm `%LOCALAPPDATA%\JayramDairy\backups\` (or `_devdata\backups\`)
   has a copy after the first successful launch with an existing DB.

As always: anything that doesn't match how the business actually runs
is worth catching now.
