# Workflow

## Install Skill Folder

Copy folder `web-playwright-e2e-bootstrap` to:

`C:\Users\<username>\.codex\skills\web-playwright-e2e-bootstrap`

## Bootstrap Command

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\<username>\.codex\skills\web-playwright-e2e-bootstrap\scripts\bootstrap-web-e2e.ps1 -ProjectPath . -InstallBrowser
```

Force overwrite existing template files:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\<username>\.codex\skills\web-playwright-e2e-bootstrap\scripts\bootstrap-web-e2e.ps1 -ProjectPath . -Force
```

## Runtime Requirements

- Node.js + npm installed
- Playwright browser binaries installed (script can install via `-InstallBrowser`)

## Output Verification

- `e2e/playwright-report/index.html`
- `e2e/self-test-reports/*.docx`
- DOCX contains screenshot images inside each test item's remarks

## Required `.env` Fields

- `E2E_BASE_URL`
- `E2E_DEMO_PATH`

## Recommended `.env` Fields

- `E2E_SCREENSHOT_MODE=on`
- `E2E_AUTO_START_SERVER=true`
- `E2E_WEB_ROOT=./`
- `E2E_DEMO_READY_SELECTOR` (optional)
- `E2E_REPORT_TEMPLATE_PATH` (optional)
