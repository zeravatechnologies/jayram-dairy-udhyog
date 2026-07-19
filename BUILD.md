# Building the Windows Installer

**Important:** this app was developed and tested in a Linux environment
(that's what built and ran all 60 tests and the screenshots you've been
reviewing). PyInstaller does **not** cross-compile — a Windows `.exe`
must be built by running PyInstaller **on an actual Windows machine**
(your own PC, or a Windows GitHub Actions runner). This document is the
step-by-step for doing that build, since it's the one remaining step
that genuinely can't happen in this sandbox.

## Prerequisites (on a Windows machine)

1. Install Python 3.12 from python.org (check "Add to PATH" during install).
2. Install Inno Setup (free): https://jrsoftware.org/isinfo.php
3. Open a command prompt in the project folder.

## Step 1 — Install dependencies

```
pip install -r requirements.txt
pip install pyinstaller
```

## Step 2 — Run the tests one more time, on the real target OS

```
pytest tests/ -v
```

All 60 should pass here too — this is a cheap, important sanity check
that nothing about the logic is platform-specific before you package it.

## Step 3 — Build the executable bundle

```
pyinstaller jayram_dairy.spec
```

This produces `dist\JayramDairyUdhyog\` — a folder containing
`JayramDairyUdhyog.exe` and everything it needs to run. Try launching
the `.exe` directly from that folder first, before building the
installer, to confirm the bundle itself works.

## Step 4 — Build the installer

Open `installer\setup.iss` in the Inno Setup Compiler and click **Build**,
or from the command line:

```
ISCC.exe installer\setup.iss
```

This produces `installer\Output\JayramDairyUdhyog-Setup-v0.5.0.exe` —
this is the one file you send to your friend.

## Step 5 — Generate the checksum

```
certutil -hashfile installer\Output\JayramDairyUdhyog-Setup-v0.5.0.exe SHA256
```

Send this alongside the download link, per `deployment-infra.md` Section 3 —
your friend can verify it with the same command before running the
installer.

## Step 6 — Distribute

Upload the `Setup.exe` as a GitHub Release on a private repo you
control (or wherever you've decided to host it), post the checksum next
to it, and send your friend the link.

## Every subsequent release

Bump `MyAppVersion` in `installer\setup.iss` and `APP_VERSION` in
`app/utils/activity_log.py` together — they should always match, since
the activity log records the version and that's the first thing you'll
ask about when troubleshooting (`deployment-infra.md` Section 4). Then
repeat Steps 1–6.

## What this sandbox already verified for you

- All 60 unit/integration tests pass
- The full app runs correctly headlessly, including login, all six
  screens, activity logging, and the AppData path logic
- The Devanagari font renders correctly when bundled
- Screenshots confirm the actual visual output at each stage

What it could **not** verify: how it actually looks and performs in a
real Windows window, on real Windows fonts/DPI scaling, on hardware
similar to the shop's PC. That first real Windows run — Step 3 above —
is worth doing carefully and comparing against the screenshots you've
already seen.
