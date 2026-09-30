# OrangeHRM Dashboard Automation

A Flask dashboard that triggers a Selenium automation flow against the
[OrangeHRM demo site](https://opensource-demo.orangehrmlive.com): log in,
add an employee, verify it, extract the employee list, and log out — all
started by clicking "Run Automation" on the dashboard, not by running a
script manually.

## Project layout

```
app.py              Flask routes (dashboard + trigger endpoint)
automation.py        All Selenium logic, heavily commented
templates/index.html Dashboard form + results view
static/style.css     Styling
logs/                One .log file per automation run
screenshots/         Before/after/error screenshots per run
exports/             CSV of extracted employee data per run
```

## Setup

```bash
cd "Dashboard automation"
python3 -m venv venv
source venv/bin/activate        # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You need Google Chrome installed. `webdriver-manager` (in requirements.txt)
downloads the matching chromedriver binary automatically — no manual driver
setup needed.

## Run

```bash
python app.py
```

Open http://127.0.0.1:5000, fill in:
- Username / password (demo default: `Admin` / `admin123`)
- First name, last name, and optionally an employee ID

Click **Run Automation**. A Chrome window will open and drive itself through
the flow (uncheck "headless" is the default so you can watch it work — check
the box once you trust it, to run without a visible browser).

## Selenium concepts, tied to the actual code

This was written as a first Selenium project, so `automation.py` doubles as
a walkthrough. Key ideas, and where to see them:

- **WebDriver** — `_get_driver()`. The `driver` object is the remote control
  for the whole browser: `driver.get(url)`, `driver.find_element(...)`,
  `driver.quit()`.

- **Locators (`By.*`)** — used everywhere elements are found:
  - `By.NAME` for standard form inputs (`username`, `firstName`) — used when
    the HTML has a stable `name` attribute.
  - `By.CSS_SELECTOR` for things like `button[type='submit']` or a class name.
  - `By.XPATH` for cases with no stable attribute — e.g. `add_employee()`
    finds the Employee Id field by walking from its visible label text,
    because it has no `name`/`id` in the markup.

- **Waits** — this is the part that usually causes "flaky" Selenium scripts.
  - **Never** use a fixed `time.sleep(5)` as your main strategy — either the
    page is slower than that (fails) or faster (wastes time).
  - `driver.implicitly_wait(3)` in `_get_driver()` is a blanket "keep
    retrying up to 3s" setting applied to every `find_element` call.
  - `WebDriverWait(driver, timeout).until(EC.some_condition(...))` is the
    explicit wait used for every meaningful step (`login`, `add_employee`,
    `logout`, etc.) — it waits for a *specific condition* like "URL contains
    /dashboard" or "element is clickable" before moving on. This is the
    pattern to reach for by default.

- **`expected_conditions` (imported as `EC`)** — prebuilt conditions passed
  into `WebDriverWait.until(...)`:
  - `EC.presence_of_element_located` — element exists in the DOM
  - `EC.element_to_be_clickable` — element is visible and enabled
  - `EC.url_contains` — used as the "did this action succeed" signal after
    login, after saving an employee, and after logout

- **try/except/finally** — every step in `run_orangehrm_flow()` is wrapped:
  if anything raises, it's logged and turned into a `status: "failed"`
  result for the dashboard instead of crashing the Flask request. The
  `finally` block always calls `driver.quit()`, so a failed run doesn't leave
  a zombie Chrome process behind.

- **Why some locators might break** — the OrangeHRM demo site is a living
  app whose markup (CSS class names especially) can shift between versions.
  If a step suddenly fails, the fix is almost always: open Chrome DevTools
  on the real page, inspect the element, and update the locator in
  `automation.py`. That debugging loop — inspect element → adjust locator →
  re-run — is the core day-to-day skill in Selenium work.

## Logs, screenshots, exports

Each run gets a timestamped `run_id`. Check:
- `logs/run_<id>.log` — step-by-step log of what happened
- `screenshots/<id>_*.png` — after login, before/after adding the employee,
  and an error screenshot if something failed
- `exports/employees_<id>.csv` — the extracted employee table

## Notes for the assignment write-up

- Credentials are never hardcoded — they're read from the submitted form on
  every request (`app.py`).
- The employee list extraction caps at 20 rows by default
  (`extract_employee_list(..., max_rows=20)`) to keep runs fast; raise that
  if the assignment expects the full list.
