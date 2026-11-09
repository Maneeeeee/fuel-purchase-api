# Python setup for this project

Python 3.12.10 is installed on this machine and wired up for this project.

## What was set up

| Item | Location |
|---|---|
| Interpreter | `C:\Users\<user>\AppData\Local\Programs\Python\Python312\python.exe` (3.12.10) |
| Project venv | `.venv\` in this folder |
| Pi extension | `.pi\extensions\python-env.ts` |

## Why `python` used to fail

Python 3.12 was installed but not first on `PATH`. The Microsoft Store
placeholder at `WindowsApps\python.exe` shadowed it and only printed
*"Python was not found; run without arguments to install from the Microsoft Store"*.

Two fixes were applied:

1. **User `PATH` reordered** so `Python312`, `Python312\Scripts`, and the
   `py` launcher come before `WindowsApps`. New terminals now resolve
   `python`, `python3`, `pip`, and `py` to the real interpreter.
   A `python3.exe` copy was also added to `Python312` (the Windows installer
   ships only `python.exe`).

2. **Pi extension** (`.pi\extensions\python-env.ts`) overrides the `bash` and
   `powershell` tools so every command runs with `.venv\Scripts` first on
   `PATH` and `VIRTUAL_ENV` set. It also recreates `.venv` automatically if it
   is deleted.

## Usage

Inside Pi, `python` / `pip` already point at the project venv — no activation
needed:

```bash
python --version          # 3.12.10
pip install -r requirements.txt
python -m pytest
```

In a plain terminal (cmd/PowerShell/Git Bash) outside Pi, use the venv
explicitly or activate it:

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1

# cmd
.venv\Scripts\activate.bat

# Git Bash
source .venv/Scripts/activate
```

To activate manually in Git Bash:

```bash
source .venv/Scripts/activate
python --version
```

## Notes

- `requirements.txt` packages are already installed in `.venv`.
- The extension resolves the project root by walking up from the working
  directory looking for `.pi` or `.venv`, so it keeps working from
  subdirectories.
- The project folder is registered as trusted in
  `~\.pi\agent\trust.json` so the extension loads without a prompt.
