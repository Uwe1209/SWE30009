"""Confirms that Chrome and a matching chromedriver are usable on this runner.

Run before the test suite so that a missing or mismatched browser fails the
workflow with a clear message, rather than surfacing later as ten identical
WebDriver errors inside the test report.

Selenium 4.6 and later ships Selenium Manager, which resolves and downloads the
chromedriver build matching the installed Chrome. That is why no separate
chromedriver setup step is needed in either workflow.
"""

import sys

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

FLAGS = (
    "--headless=new",
    "--no-sandbox",            # required when the runner executes as root (Linux)
    "--disable-dev-shm-usage", # avoids the small /dev/shm on container runners
    "--disable-gpu",
)


def main():
    options = Options()
    for flag in FLAGS:
        options.add_argument(flag)

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as exc:
        print("Browser check FAILED.")
        print("Chrome or chromedriver could not be started on this runner.")
        print("Error: %s" % exc)
        return 1

    caps = driver.capabilities
    driver_version = caps.get("chrome", {}).get("chromedriverVersion", "unknown")

    print("Browser check passed.")
    print("  Chrome       : %s" % caps.get("browserVersion", "unknown"))
    print("  chromedriver : %s" % driver_version.split(" ")[0])
    print("  Platform     : %s" % caps.get("platformName", "unknown"))

    driver.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
