"""
SWE30009 Project - Extension Task 3
Builds an HTML test report from the results written by test_gateway.py.

Reads test_results.csv and produces:
  * test-report.html - a standalone report with charts and colour-coded results
  * summary.md       - a short digest for the GitHub Actions run summary

Everything is drawn with inline SVG and inline CSS, so the report opens
correctly straight from the downloaded artifact with no network access and
no external libraries.

Usage:
    python tests/generate_report.py --platform ubuntu-latest
"""

import argparse
import csv
import html
import os
import sys
from datetime import datetime, timezone

DEFAULT_RESULTS = "test_results.csv"
DEFAULT_OUT = "test-report.html"
DEFAULT_SUMMARY = "summary.md"

PALETTE = {
    "PASS": "#1c7a4a",
    "FAIL": "#b3261e",
    "ERROR": "#8a5a00",
}


# ----------------------------------------------------------------------
# Input
# ----------------------------------------------------------------------

def read_results(path):
    if not os.path.exists(path):
        return None
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def summarise(rows):
    total = len(rows)
    passed = sum(1 for r in rows if r.get("status") == "PASS")
    failed = sum(1 for r in rows if r.get("status") == "FAIL")
    errored = sum(1 for r in rows if r.get("status") == "ERROR")

    seconds = 0.0
    for r in rows:
        try:
            seconds += float(r.get("seconds") or 0)
        except ValueError:
            pass

    rate = (passed / total * 100.0) if total else 0.0
    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "errored": errored,
        "seconds": round(seconds, 2),
        "rate": round(rate, 1),
    }


# ----------------------------------------------------------------------
# SVG charts
# ----------------------------------------------------------------------

def donut(stats):
    """Pass/fail ring. Drawn with stroke-dasharray on a single circle."""
    radius = 54
    circumference = 2 * 3.14159265 * radius
    rate = stats["rate"] / 100.0
    filled = circumference * rate
    gap = circumference - filled

    return """
<svg viewBox="0 0 140 140" width="150" height="150" role="img"
     aria-label="Pass rate {rate} percent">
  <circle cx="70" cy="70" r="{r}" fill="none" stroke="#e6e9ee" stroke-width="16"/>
  <circle cx="70" cy="70" r="{r}" fill="none" stroke="{colour}" stroke-width="16"
          stroke-dasharray="{filled:.2f} {gap:.2f}"
          stroke-dashoffset="{offset:.2f}" stroke-linecap="butt"
          transform="rotate(-90 70 70)"/>
  <text x="70" y="66" text-anchor="middle" font-size="25" font-weight="700"
        fill="#1c2128">{rate:.0f}%</text>
  <text x="70" y="88" text-anchor="middle" font-size="12" fill="#5b6472">passed</text>
</svg>""".format(
        r=radius,
        colour=PALETTE["PASS"] if stats["rate"] == 100 else PALETTE["FAIL"],
        filled=filled,
        gap=gap,
        offset=0,
        rate=stats["rate"],
    )


def duration_bars(rows):
    """Horizontal bar chart of per-test execution time."""
    if not rows:
        return "<p class='muted'>No timing data available.</p>"

    values = []
    for r in rows:
        try:
            values.append(float(r.get("seconds") or 0))
        except ValueError:
            values.append(0.0)

    longest = max(values) or 1.0
    row_height = 26
    label_w = 62
    track_w = 430
    height = row_height * len(rows) + 16

    parts = ['<svg viewBox="0 0 560 %d" width="100%%" height="%d" role="img" '
             'aria-label="Execution time per test case">' % (height, height)]

    for i, (r, secs) in enumerate(zip(rows, values)):
        y = 8 + i * row_height
        width = max(2.0, (secs / longest) * track_w)
        colour = PALETTE.get(r.get("status"), "#8a93a0")

        parts.append(
            '<text x="0" y="%d" font-size="12" fill="#5b6472">%s</text>'
            % (y + 13, html.escape(r.get("test_id", "?")))
        )
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="14" rx="3" fill="#eef0f3"/>'
            % (label_w, y + 3, track_w)
        )
        parts.append(
            '<rect x="%d" y="%d" width="%.1f" height="14" rx="3" fill="%s"/>'
            % (label_w, y + 3, width, colour)
        )
        parts.append(
            '<text x="%d" y="%d" font-size="11.5" fill="#5b6472">%.2fs</text>'
            % (label_w + track_w + 8, y + 13, secs)
        )

    parts.append("</svg>")
    return "".join(parts)


# ----------------------------------------------------------------------
# HTML assembly
# ----------------------------------------------------------------------

CSS = """
*{box-sizing:border-box}
body{margin:0;background:#f4f5f7;color:#1c2128;
     font-family:"Segoe UI",-apple-system,Roboto,Arial,sans-serif;font-size:15px;line-height:1.5}
.wrap{max-width:980px;margin:0 auto;padding:32px 26px 56px}
h1{margin:0;font-size:22px}
h2{margin:0 0 14px;font-size:16px}
.sub{margin:4px 0 0;color:#5b6472;font-size:13.5px}
.meta{margin-top:10px;display:flex;flex-wrap:wrap;gap:8px}
.chip{background:#fff;border:1px solid #e2e5ea;border-radius:99px;
      padding:3px 12px;font-size:12.5px;color:#5b6472}
.chip b{color:#1c2128;font-weight:600}
.card{background:#fff;border:1px solid #e2e5ea;border-radius:10px;padding:18px 20px;
      margin-top:20px;box-shadow:0 1px 2px rgba(20,28,40,.05)}
.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:22px}
.stat{background:#fff;border:1px solid #e2e5ea;border-radius:10px;padding:14px 16px;
      box-shadow:0 1px 2px rgba(20,28,40,.05)}
.stat .n{font-size:26px;font-weight:700;line-height:1.2}
.stat .k{font-size:12px;text-transform:uppercase;letter-spacing:.6px;color:#8a93a0;margin-top:2px}
.split{display:grid;grid-template-columns:190px 1fr;gap:24px;align-items:center}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.5px;
   color:#8a93a0;padding:9px 10px;border-bottom:1px solid #e2e5ea;background:#fafbfc}
td{padding:9px 10px;border-bottom:1px solid #eef0f3;vertical-align:top}
tr:last-child td{border-bottom:none}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.badge{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;font-weight:600;color:#fff}
.row-fail{background:#fdf4f3}
.muted{color:#8a93a0;font-size:13.5px}
.fail-item{padding:10px 12px;border-left:3px solid #b3261e;background:#fdf4f3;
           border-radius:0 6px 6px 0;margin-bottom:10px}
.fail-item .id{font-weight:650}
.fail-item .why{font-size:13px;color:#5b6472;margin-top:2px}
footer{margin-top:28px;text-align:center;color:#8a93a0;font-size:12.5px}
@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}.split{grid-template-columns:1fr}}
"""


def badge(status):
    colour = PALETTE.get(status, "#8a93a0")
    return '<span class="badge" style="background:%s">%s</span>' % (colour, html.escape(status))


def build_html(rows, stats, platform, generated):
    failing = [r for r in rows if r.get("status") in ("FAIL", "ERROR")]

    body_rows = []
    for r in rows:
        status = r.get("status", "")
        cls = ' class="row-fail"' if status in ("FAIL", "ERROR") else ""
        body_rows.append(
            "<tr%s><td><b>%s</b></td><td>%s</td><td>%s</td>"
            "<td class='num'>%s</td><td class='num'>%s</td>"
            "<td class='num'>%s</td><td>%s</td></tr>" % (
                cls,
                html.escape(r.get("test_id", "")),
                html.escape(r.get("description", "")),
                html.escape(r.get("batch_api", "")),
                html.escape(r.get("expected_total", "")),
                html.escape(r.get("actual_total", "") or "-"),
                html.escape(r.get("seconds", "")),
                badge(status),
            )
        )

    if failing:
        fail_block = "".join(
            '<div class="fail-item"><div class="id">%s &mdash; %s</div>'
            '<div class="why">%s</div></div>' % (
                html.escape(r.get("test_id", "")),
                html.escape(r.get("status", "")),
                html.escape(r.get("notes") or "No reason recorded."),
            )
            for r in failing
        )
    else:
        fail_block = '<p class="muted">No failures. Every test case matched its expected result.</p>'

    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LLM AI Gateway - Test Report</title>
<style>%(css)s</style></head><body><div class="wrap">

<header>
  <h1>LLM AI Gateway &mdash; Automated Test Report</h1>
  <p class="sub">SWE30009 Software Testing and Reliability</p>
  <div class="meta">
    <span class="chip">Platform <b>%(platform)s</b></span>
    <span class="chip">Generated <b>%(generated)s</b></span>
    <span class="chip">Suite <b>Selenium functional tests</b></span>
  </div>
</header>

<div class="cards">
  <div class="stat"><div class="n">%(total)d</div><div class="k">Total tests</div></div>
  <div class="stat"><div class="n" style="color:%(pass_colour)s">%(passed)d</div><div class="k">Passed</div></div>
  <div class="stat"><div class="n" style="color:%(fail_colour)s">%(failed)d</div><div class="k">Failed</div></div>
  <div class="stat"><div class="n">%(seconds).2fs</div><div class="k">Total duration</div></div>
</div>

<div class="card">
  <h2>Outcome</h2>
  <div class="split">
    <div>%(donut)s</div>
    <div>
      <h2 style="margin-bottom:8px">Execution time per test case</h2>
      %(bars)s
    </div>
  </div>
</div>

<div class="card">
  <h2>Results</h2>
  <table>
    <thead><tr>
      <th>ID</th><th>Description</th><th>Batch</th>
      <th style="text-align:right">Expected</th><th style="text-align:right">Actual</th>
      <th style="text-align:right">Time</th><th>Status</th>
    </tr></thead>
    <tbody>%(rows)s</tbody>
  </table>
</div>

<div class="card">
  <h2>Failures</h2>
  %(fails)s
</div>

<footer>Generated automatically by generate_report.py as part of the CI pipeline.</footer>
</div></body></html>""" % {
        "css": CSS,
        "platform": html.escape(platform),
        "generated": html.escape(generated),
        "total": stats["total"],
        "passed": stats["passed"],
        "failed": stats["failed"] + stats["errored"],
        "seconds": stats["seconds"],
        "pass_colour": PALETTE["PASS"],
        "fail_colour": PALETTE["FAIL"] if (stats["failed"] + stats["errored"]) else "#1c2128",
        "donut": donut(stats),
        "bars": duration_bars(rows),
        "rows": "".join(body_rows),
        "fails": fail_block,
    }


def build_summary(stats, platform, generated):
    lines = [
        "## Selenium test run - %s" % platform,
        "",
        "| Metric | Value |",
        "| --- | --- |",
        "| Total tests | %d |" % stats["total"],
        "| Passed | %d |" % stats["passed"],
        "| Failed | %d |" % (stats["failed"] + stats["errored"]),
        "| Pass rate | %.1f%% |" % stats["rate"],
        "| Total duration | %.2fs |" % stats["seconds"],
        "| Generated | %s |" % generated,
        "",
        "The full HTML report is attached to this run as a build artifact.",
    ]
    return "\n".join(lines) + "\n"


def missing_results_html(path, platform, generated):
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>LLM AI Gateway - Test Report</title><style>%s</style></head>
<body><div class="wrap">
<h1>LLM AI Gateway &mdash; Automated Test Report</h1>
<p class="sub">Platform %s &middot; generated %s</p>
<div class="card"><h2>No results were produced</h2>
<p class="muted">The results file <code>%s</code> was not found, so the test run
did not reach the point of writing its outcome. Check the workflow log for the
step that failed.</p></div>
</div></body></html>""" % (CSS, html.escape(platform), html.escape(generated), html.escape(path))


# ----------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Build the HTML test report.")
    parser.add_argument("--results", default=DEFAULT_RESULTS)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--platform", default="local")
    args = parser.parse_args()

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    rows = read_results(args.results)

    if rows is None:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(missing_results_html(args.results, args.platform, generated))
        with open(args.summary, "w", encoding="utf-8") as handle:
            handle.write("## Selenium test run - %s\n\nNo results file was produced.\n"
                         % args.platform)
        print("No results file at '%s'. Placeholder report written to %s."
              % (args.results, args.out))
        return 0

    stats = summarise(rows)

    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(build_html(rows, stats, args.platform, generated))
    with open(args.summary, "w", encoding="utf-8") as handle:
        handle.write(build_summary(stats, args.platform, generated))

    print("Report written to %s" % args.out)
    print("  platform : %s" % args.platform)
    print("  total    : %d" % stats["total"])
    print("  passed   : %d" % stats["passed"])
    print("  failed   : %d" % (stats["failed"] + stats["errored"]))
    print("  duration : %.2fs" % stats["seconds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
