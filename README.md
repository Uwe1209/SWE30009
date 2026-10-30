# LLM AI Gateway — Automated Test Suite

[![Selenium Tests (Ubuntu)](https://github.com/Uwe1209/SWE30009.git/actions/workflows/test-ubuntu.yml/badge.svg)](https://github.com/Uwe1209/SWE30009.git/actions/workflows/test-ubuntu.yml)
[![Selenium Tests (Windows)](https://github.com/Uwe1209/SWE30009.git/actions/workflows/test-windows.yml/badge.svg)](https://github.com/Uwe1209/SWE30009.git/actions/workflows/test-windows.yml)

SWE30009 Software Testing and Reliability — project submission.

A small web application that calculates monthly LLM API usage costs, together
with a Selenium functional test suite that runs locally and on two CI runners.

## What is here

| Path | Purpose |
| --- | --- |
| `app/` | The web application: HTML, CSS and JavaScript, no build step |
| `tests/test_gateway.py` | Selenium suite; reads test cases from CSV, reports pass/fail |
| `tests/test_cases.csv` | The ten test cases and their expected results |
| `tests/check_browser.py` | Pre-flight check that Chrome and chromedriver work |
| `tests/generate_report.py` | Builds the HTML test report from the run results |
| `.github/workflows/` | The two CI pipelines |

## Running it locally

```bash
pip install -r requirements.txt

# terminal 1 — serve the application
python -m http.server 8000 --directory app

# terminal 2 — run the suite
python tests/test_gateway.py --url http://localhost:8000/index.html \
                             --csv tests/test_cases.csv
```

Add `--headless` to run without a visible browser window.

The suite writes `test_results.csv` and a screenshot per test case into
`screenshots/`. To build the HTML report from those results:

```bash
python tests/generate_report.py --platform local
```

## Running it in CI

Both workflows are manual. Open the **Actions** tab, pick a workflow, and use
**Run workflow**. Each one checks out the code, installs Python and the
dependencies, verifies the browser, serves the application, runs the suite,
builds the HTML report and uploads it as a build artifact.

The report is attached to every run under **Artifacts**, whether the run passed
or failed. A condensed table is also written to the run summary page.

## Notes on cross-platform consistency

The application, the test script and the test data are identical on both
runners. Only the setup steps differ:

- **Starting the server.** Bash backgrounds a process with a trailing `&`;
  PowerShell has no equivalent, so the Windows workflow uses `Start-Process`.
- **Polling for readiness.** `curl` on Linux, `Invoke-WebRequest` on Windows.
  Neither workflow uses a fixed sleep, which would be slower and less reliable.
- **Line continuation.** `\` in bash, a backtick in PowerShell.
- **Console encoding.** The Windows job sets `PYTHONIOENCODING=utf-8` so its
  console output matches the Linux run byte for byte.
- **Line endings.** `.gitattributes` forces LF for `.py` and `.csv` so the
  checked-out test data is identical on both platforms.
