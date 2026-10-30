"""
SWE30009 Software Testing and Reliability - Project Report
Automated functional test suite for the LLM AI Gateway Dashboard.

Reads test cases from a CSV file, drives the web application with Selenium,
compares the calculated bill against the expected result, and reports the
pass/fail status of every case.

Usage:
    python test_gateway.py
    python test_gateway.py --url http://localhost:8000/index.html
    python test_gateway.py --headless
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

DEFAULT_URL = "http://localhost:8000/index.html"
DEFAULT_CSV = "test_cases.csv"
SHOT_DIR = "screenshots"
RESULTS_CSV = "test_results.csv"
WAIT_SECONDS = 10

# Must match the model ids rendered by app.js
MODEL_IDS = [
    "claude-fable",
    "claude-haiku",
    "gpt6-astra",
    "gpt6-mini",
    "gemini3-pro",
    "gemini3-flash",
    "deepseek-flash",
    "mistral-large",
]

LINE = "=" * 70


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def to_bool(text):
    """Interpret the batch_api column of the CSV."""
    return str(text).strip().upper() in ("TRUE", "YES", "1", "Y")


def money_to_number(text):
    """Turn the on-screen 'RM 27.56' into the string '27.56'.

    Strips the currency prefix and any thousands separators so the
    comparison is made on the number alone.
    """
    cleaned = str(text).replace("RM", "").replace(",", "").strip()
    return cleaned


def load_test_cases(path):
    """Read the test cases, failing loudly if the file is unusable."""
    if not os.path.exists(path):
        raise FileNotFoundError("Test case file not found: %s" % path)

    with open(path, newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    if not rows:
        raise ValueError("Test case file '%s' contains no test cases." % path)

    required = ["test_id", "batch_api", "expected_total"]
    missing = [col for col in required if col not in rows[0]]
    if missing:
        raise ValueError("Test case file is missing column(s): %s" % ", ".join(missing))

    return rows


def build_driver(headless):
    """Create the Chrome WebDriver, with a clear message if it cannot start."""
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1400,1000")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")

    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise WebDriverException(
            "Could not start Chrome. Check that Chrome and a matching "
            "chromedriver are installed and on PATH.\nOriginal error: %s" % exc
        )


# ----------------------------------------------------------------------
# Driving the application
# ----------------------------------------------------------------------

def load_page(driver, url):
    """Navigate to the application and wait until it is interactive."""
    driver.get(url)
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.element_to_be_clickable((By.ID, "calculate-btn"))
    )
    # The model rows are injected by JavaScript, so wait for the first input.
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.presence_of_element_located((By.ID, "usage-" + MODEL_IDS[0]))
    )


def enter_usage(driver, case):
    """Type the usage figure for every model listed in the test case."""
    for model_id in MODEL_IDS:
        value = case.get(model_id, "0")
        value = "0" if value is None or str(value).strip() == "" else str(value).strip()

        field = driver.find_element(By.ID, "usage-" + model_id)
        field.clear()
        field.send_keys(value)


def set_batch_toggle(driver, wanted):
    """Switch the batch API discount on or off.

    The checkbox itself is visually hidden behind a styled switch, so the
    visible track is clicked instead. The checkbox state is still read
    directly, which is what decides whether a click is needed at all.
    """
    checkbox = driver.find_element(By.ID, "batch-api")
    if checkbox.is_selected() != wanted:
        driver.find_element(
            By.CSS_SELECTOR, "label[for='batch-api'] .switch-track"
        ).click()

    if checkbox.is_selected() != wanted:
        raise AssertionError("Batch API toggle did not reach the required state.")


def read_results(driver):
    """Wait for the summary panel, then read the figures off the page."""
    WebDriverWait(driver, WAIT_SECONDS).until(
        EC.visibility_of_element_located((By.ID, "results-body"))
    )

    total = driver.find_element(By.ID, "total-amount").text
    subtotal = driver.find_element(By.ID, "subtotal-amount").text
    sst = driver.find_element(By.ID, "sst-amount").text
    models_used = driver.find_element(By.ID, "models-used-count").text

    return {
        "total": money_to_number(total),
        "subtotal": money_to_number(subtotal),
        "sst": money_to_number(sst),
        "models_used": models_used.strip(),
    }


def capture(driver, test_id):
    """Save a screenshot of the application showing the final bill."""
    os.makedirs(SHOT_DIR, exist_ok=True)
    path = os.path.join(SHOT_DIR, "%s.png" % test_id)
    try:
        driver.save_screenshot(path)
        return path
    except WebDriverException:
        return "(screenshot failed)"


# ----------------------------------------------------------------------
# One test case
# ----------------------------------------------------------------------

def run_case(driver, url, case):
    """Execute a single test case and return a result dictionary."""
    test_id = case["test_id"].strip()
    description = (case.get("description") or "").strip()
    batch = to_bool(case["batch_api"])
    expected_total = str(case["expected_total"]).strip()
    expected_models = str(case.get("expected_models_used", "")).strip()

    result = {
        "test_id": test_id,
        "description": description,
        "batch_api": "ON" if batch else "OFF",
        "expected_total": expected_total,
        "actual_total": "",
        "expected_models_used": expected_models,
        "actual_models_used": "",
        "status": "ERROR",
        "notes": "",
        "screenshot": "",
        "seconds": 0.0,
    }

    started = time.time()

    try:
        load_page(driver, url)
        enter_usage(driver, case)
        set_batch_toggle(driver, batch)

        driver.find_element(By.ID, "calculate-btn").click()

        actual = read_results(driver)
        result["actual_total"] = actual["total"]
        result["actual_models_used"] = actual["models_used"]
        result["screenshot"] = capture(driver, test_id)

        problems = []
        if actual["total"] != expected_total:
            problems.append(
                "total expected %s but got %s" % (expected_total, actual["total"])
            )
        if expected_models and actual["models_used"] != expected_models:
            problems.append(
                "models used expected %s but got %s"
                % (expected_models, actual["models_used"])
            )

        result["status"] = "FAIL" if problems else "PASS"
        result["notes"] = "; ".join(problems)

    except TimeoutException:
        result["notes"] = "Timed out waiting for the billing summary to appear."
        result["screenshot"] = capture(driver, test_id)
    except NoSuchElementException as exc:
        result["notes"] = "Expected element not found: %s" % exc.msg
        result["screenshot"] = capture(driver, test_id)
    except AssertionError as exc:
        result["notes"] = str(exc)
        result["screenshot"] = capture(driver, test_id)
    except WebDriverException as exc:
        result["notes"] = "WebDriver error: %s" % exc
    except Exception as exc:                      # catch-all so the run continues
        result["notes"] = "Unexpected error: %r" % exc

    result["seconds"] = round(time.time() - started, 2)
    return result


def print_case(result):
    """Print one test case block to the console."""
    print("[%s] %s" % (result["test_id"], result["description"]))
    print("       batch API       : %s" % result["batch_api"])
    print("       expected total  : RM %s" % result["expected_total"])
    print("       actual total    : RM %s" % (result["actual_total"] or "-"))
    print("       expected models : %s" % (result["expected_models_used"] or "-"))
    print("       actual models   : %s" % (result["actual_models_used"] or "-"))
    print("       screenshot      : %s" % (result["screenshot"] or "-"))
    if result["notes"]:
        print("       notes           : %s" % result["notes"])
    print("       RESULT          : %s  (%.2fs)" % (result["status"], result["seconds"]))
    print()


def write_results(results, path):
    """Save the run to a CSV so the outcome is available after the console scrolls."""
    columns = [
        "test_id", "description", "batch_api",
        "expected_total", "actual_total",
        "expected_models_used", "actual_models_used",
        "status", "seconds", "notes", "screenshot",
    ]
    try:
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in results:
                writer.writerow({col: row.get(col, "") for col in columns})
        return path
    except OSError as exc:
        print("Warning: could not write results file (%s)" % exc)
        return None


# ----------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automated functional tests for the LLM AI Gateway Dashboard."
    )
    parser.add_argument("--url", default=DEFAULT_URL, help="Application URL")
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Test case CSV file")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser")
    args = parser.parse_args()

    try:
        cases = load_test_cases(args.csv)
    except (FileNotFoundError, ValueError) as exc:
        print("Cannot start the test run: %s" % exc)
        return 2

    print(LINE)
    print(" LLM AI Gateway - Automated Functional Test Run")
    print(LINE)
    print(" Target URL : %s" % args.url)
    print(" Test cases : %s (%d cases)" % (args.csv, len(cases)))
    print(" Browser    : Chrome (%s)" % ("headless" if args.headless else "headed"))
    print(" Started    : %s" % datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print(LINE)
    print()

    try:
        driver = build_driver(args.headless)
    except WebDriverException as exc:
        print("Cannot start the test run: %s" % exc)
        return 2

    results = []
    run_started = time.time()

    try:
        for case in cases:
            result = run_case(driver, args.url, case)
            results.append(result)
            print_case(result)
    finally:
        driver.quit()

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")
    errored = sum(1 for r in results if r["status"] == "ERROR")
    duration = round(time.time() - run_started, 2)

    saved = write_results(results, RESULTS_CSV)

    print(LINE)
    print(" SUMMARY")
    print(LINE)
    print(" Total    : %d" % len(results))
    print(" Passed   : %d" % passed)
    print(" Failed   : %d" % failed)
    print(" Errors   : %d" % errored)
    print(" Duration : %.2fs" % duration)
    if saved:
        print(" Results  : %s" % saved)
    print(" Screenshots in: %s/" % SHOT_DIR)
    print(LINE)

    return 0 if (failed == 0 and errored == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
