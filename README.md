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

**Data:** SQLite, stored under the real Windows AppData location when
packaged (`%LOCALAPPDATA%\JayramDairy\`), or a local `_devdata/` folder
when running from source for development.

## What's NOT in here yet (honestly)

- Nepali BS *input* on date fields — dates display in BS everywhere,
  but entry still uses the system date. Worth a follow-up pass.
- Automatic local backups (the deployment doc specifies these; the
  mechanism isn't wired in yet).
- Alembic migrations aren't set up yet — the schema is created fresh
  via `create_all()`. Fine for this stage; needed before the first real
  schema change ships to your friend's machine.
- The actual Windows `.exe` — see `BUILD.md`. PyInstaller can't
  cross-compile from this Linux sandbox; that step has to run on a real
  Windows machine, with clear step-by-step instructions provided.

## Running it yourself

```bash
pip install -r requirements.txt
python app/main.py
```

First launch: create an account (any username/password, 4+ characters).
Subsequent launches: sign in with what you created. Seeds 2 vendors,
3 products, 2 customers on first run.

## Running the tests

```bash
pytest tests/ -v
```

60 tests, all passing — covering pricing, balance, production pool,
orders/stock, payments, auth, activity logging, and dashboard stats,
including several regression tests for real bugs caught while building
(an ID-collision bug between vendor and order payments, and a log
double-writing bug).

## Building the real Windows installer

See `BUILD.md` for the full step-by-step — needs to run on an actual
Windows machine, not this sandbox.

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

As always: anything that doesn't match how your friend's business
actually runs is worth catching now.
# jayram-dairy-udhyog
