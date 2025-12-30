# Packaging (Phase 0/1)

This folder contains unsigned build steps for local installers on macOS and Windows.

## Phase 0: Pre-signing builds (unsigned)

Unsigned builds are for internal testing only. macOS Gatekeeper and Windows SmartScreen
will warn on first launch.

## Phase 1: Bundled app packaging (PyInstaller)

The scripts below bundle Python and dependencies into a standalone app:

### macOS

```bash
./packaging/scripts/build-macos.sh
```

Outputs:
- `dist/SHARP Studio.app`
- `dist/SHARP-Studio-unsigned.dmg`

### macOS debug run

```bash
./packaging/scripts/run-macos-debug.sh
```

This starts the GUI with verbose logs. Set `SHARP_GUI_NO_BROWSER=1` to skip
auto-opening the browser.

### Windows (PowerShell)

```powershell
.\packaging\scripts\build-windows.ps1
```

Output:
- `dist/SHARP Studio\`

## Notes

- The GUI launcher auto-opens the browser unless `--no-browser` is provided.
- Optional environment overrides:
  - `SHARP_GUI_HOST`
  - `SHARP_GUI_PORT`
  - `SHARP_GUI_OUTPUT_ROOT`

If PyInstaller misses a module, add it to `packaging/pyinstaller/sharp-studio.spec`
under `hiddenimports`.
