"""Report layout for the whole suite (reports/report.html).

The pytest-html "Links" column is dropped: this project attaches no links. Each test's exchange
log is an inline block in its expanded row (tests/e2e/conftest.py).
"""


def pytest_html_results_table_header(cells):
    cells[:] = [cell for cell in cells if cell != "<th>Links</th>"]


def pytest_html_results_table_row(report, cells):
    cells[:] = [cell for cell in cells if 'class="col-links"' not in cell]
