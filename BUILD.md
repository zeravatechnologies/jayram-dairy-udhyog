# Building the Windows Installer

**Important:** PyInstaller does **not** cross-compile — a Windows `.exe`
must be built by running PyInstaller **on an actual Windows machine**.

## Prerequisites (on a Windows machine)

1. Install Python 3.12 from **python.org** (check "Add to PATH" during install).
   Prefer a clean venv from that install — **do not build the release
   installer from an Anaconda/Miniconda env if you can avoid it**. Conda
   puts its own DLLs on PATH, which can hide packaging bugs that only
   appear on a shop PC (or any machine without Anaconda).
2. Install Inno Setup (free): https://jrsoftware.org/isinfo.php
3. Open a command prompt in the project folder (`jayram-dairy`).

## Every release (checklist)

1. Bump **both** version strings so they always match:
   - `MyAppVersion` in `installer\setup.iss`
   - `APP_VERSION` in `app\utils\activity_log.py`
2. Run the tests: `pytest tests/ -v`
3. Build the exe bundle (Step 3 below).
4. **Smoke-test the `.exe` before making the installer** (Step 3a).
5. Build the installer (Step 4 below).
6. Generate the SHA256 checksum (Step 5 below).
7. Upload `Setup.exe` + checksum as a GitHub Release (private repo is fine).

## Step 1 — Install dependencies

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` pins **both** `PyQt6` and `PyQt6-Qt6` to the same
version. Do not let pip float `PyQt6-Qt6` ahead of `PyQt6` — a mismatch
causes:

```
ImportError: DLL load failed while importing QtWidgets:
The specified procedure could not be found.
```

## Step 2 — Run the tests on Windows

```
pytest tests/ -v
```

## Step 3 — Build the executable bundle

```
pyinstaller jayram_dairy.spec
```

This produces `dist\JayramDairyUdhyog\` — a folder containing
`JayramDairyUdhyog.exe` and everything it needs (including Alembic
migration scripts).

### Step 3a — Smoke-test (required)

1. Double-click `dist\JayramDairyUdhyog\JayramDairyUdhyog.exe` and confirm
   the login window appears (no "Unhandled exception" dialog).
2. Also test with a **clean PATH** so Anaconda cannot mask DLL problems.
   From PowerShell:

```
$exe = "$PWD\dist\JayramDairyUdhyog\JayramDairyUdhyog.exe"
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $exe
$psi.WorkingDirectory = Split-Path $exe
$psi.UseShellExecute = $false
$psi.EnvironmentVariables["PATH"] = "C:\Windows\System32;C:\Windows"
[System.Diagnostics.Process]::Start($psi)
```

If this fails with a Qt/`QtWidgets` DLL error, fix dependencies and rebuild
**before** running Inno Setup or publishing a GitHub Release.

## Step 4 — Build the installer

```
ISCC.exe installer\setup.iss
```

Or open `installer\setup.iss` in the Inno Setup Compiler and click **Build**.

Output: `installer\Output\JayramDairyUdhyog-Setup-v0.5.4.exe`

## Step 5 — Generate the checksum

```
certutil -hashfile installer\Output\JayramDairyUdhyog-Setup-v0.5.4.exe SHA256
```

Send this alongside the download link so the shop PC can verify before install.

## Step 6 — Distribute

Upload the `Setup.exe` as a GitHub Release, post the checksum next to it,
and send the link to the user.

---

## Upgrading on the shop PC (future releases)

The installer uses a stable `AppId` and leaves business data in
`%LOCALAPPDATA%\JayramDairy\` (database, `backups\`, `logs\`). Installing
a newer Setup.exe replaces the program files only.

1. Close Jayram Dairy Udhyog completely.
2. Run the new `JayramDairyUdhyog-Setup-vX.Y.Z.exe`.
3. Launch the app, sign in, and open **Activity Log** — the version column
   should show the new `APP_VERSION`.
4. Spot-check one vendor balance and one recent payment.

### If something looks wrong after an upgrade

1. Close the app.
2. Open `%LOCALAPPDATA%\JayramDairy\backups\`
3. Copy the newest `jayram_dairy_*.db` over
   `%LOCALAPPDATA%\JayramDairy\jayram_dairy.db` (replace the live file).
4. Restart the app.

The app also creates a backup before schema migrations and once per day
on launch (keeping the last 10 backup files).

---

## First install notes

- Packaged installs **do not** load demo vendors/products/customers.
  After creating an account, add real masters from the screens.
- Demo seed data only appears when running from source (`python app/main.py`).

## What this sandbox already verified

- Unit/integration tests including migrations, backups, and seed gating
- AppData path logic, activity logging, Devanagari font bundling

What still needs a real Windows smoke test after you build: DPI scaling,
antivirus/SmartScreen prompts (unsigned builds will warn), and a full
click-through on hardware similar to the shop PC.
