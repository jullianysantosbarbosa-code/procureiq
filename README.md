# ProcureIQ

[![CI](https://github.com/jullianysantosbarbosa-code/procureiq/actions/workflows/ci.yml/badge.svg)](https://github.com/jullianysantosbarbosa-code/procureiq/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

A command-line tool that turns raw procurement records into answers: where the money goes, how long each type of purchase takes, and which purchases deserve a second look.

I built it from my background in public-sector procurement, where the same questions came up every month and were answered by hand in spreadsheets. ProcureIQ automates them with Python and SQL. **All data in this repository is synthetic**: no real suppliers, contracts or government records are used.

## Features

- **Spend analysis**: total spend by supplier (with share of total) and by month.
- **Lead times**: median, mean and maximum processing time per category.
- **Red-flag detection**
  - *Possible split purchases*: several purchases from the same supplier, department and category that are each below an approval threshold but together exceed it.
  - *Unusual purchases*: amounts far above the normal range for their category, using a robust quartile-based rule.
- **Validated CSV import** with clear, line-numbered error messages. Invalid files never partially load.
- **Table or JSON output** for every report, so results can feed other tools.
- **Synthetic data generator**, deterministic for a given seed.
- **Zero third-party dependencies**: standard library only (`sqlite3`, `argparse`, `statistics`).

## Quick start

```bash
git clone https://github.com/jullianysantosbarbosa-code/procureiq.git
cd procureiq
python -m pip install -e .

procureiq summary data/sample_procurements.csv
```

Requires Python 3.10 or later. You can also run it without installing: `PYTHONPATH=src python -m procureiq summary data/sample_procurements.csv`.

## Usage

```text
procureiq generate [--rows N] [--seed N] [--out PATH]
procureiq summary     CSV [--json]
procureiq suppliers   CSV [--top N] [--json]
procureiq monthly     CSV [--json]
procureiq lead-times  CSV [--json]
procureiq flags       CSV [--threshold EUR] [--window DAYS] [--json]
procureiq outliers    CSV [--k MULTIPLIER] [--json]
```

### Headline numbers

```text
$ procureiq summary data/sample_procurements.csv
Records:            612
Period:             2024-01-01 to 2025-12-30
Total spend (EUR):  9,027,377.23
Top suppliers:      Northwind Digital (20.2%), Liffey Consulting Group (14.7%), Atlas Cloud Services (13.2%)
Possible split purchases: 6
Unusual purchases:        3
```

### Spend by supplier

```text
$ procureiq suppliers data/sample_procurements.csv --top 5
Supplier                  Spend (EUR)  Orders  Share %
-----------------------  ------------  ------  -------
Northwind Digital        1,826,903.14     121     20.2
Liffey Consulting Group  1,328,038.25      95     14.7
Atlas Cloud Services     1,194,075.72      83     13.2
Harbour Office Supplies  1,003,460.54      67     11.1
Emerald Facilities Ltd     994,527.87      63     11.0
```

### Processing time by category

```text
$ procureiq lead-times data/sample_procurements.csv
Category         Orders  Median days  Mean days  Max days
---------------  ------  -----------  ---------  --------
Consulting          124         47.0       45.8        70
IT Services         111         25.0       25.7        45
Facilities          107         19.0       19.0        30
Training            135         15.0       15.1        25
Office Supplies     135          6.0        5.8        10
```

### Possible split purchases

```text
$ procureiq flags data/sample_procurements.csv
Supplier                  Department  Category     From        To          Orders  Total (EUR)
------------------------  ----------  -----------  ----------  ----------  ------  -----------
Northwind Digital         Legal       Consulting   2025-01-07  2025-01-28       2    72,953.13
Northwind Digital         Legal       IT Services  2024-04-28  2024-05-03       3    68,608.10
Celtic Training Partners  IT          Consulting   2024-05-01  2024-05-06       2    67,723.76
Liffey Consulting Group   HR          IT Services  2025-01-25  2025-01-31       3    64,317.00
Atlas Cloud Services      Legal       IT Services  2024-06-10  2024-06-30       2    64,156.70
Northwind Digital         Operations  IT Services  2025-11-14  2025-11-20       3    62,266.48
```

### Unusual purchases

```text
$ procureiq outliers data/sample_procurements.csv
 ID  Date        Supplier                 Category         Amount (EUR)  Upper fence (EUR)
---  ----------  -----------------------  ---------------  ------------  -----------------
433  2025-06-19  Harbour Office Supplies  Office Supplies     37,587.53           5,878.57
321  2025-02-08  Harbour Office Supplies  Office Supplies     32,025.22           5,878.57
479  2025-08-09  Harbour Office Supplies  Office Supplies     31,715.15           5,878.57
```

## How the red-flag detection works

**Split purchases.** Procurement rules often require a more formal process above a value threshold, which creates an incentive to split one large purchase into smaller ones. For each supplier, department and category, ProcureIQ sorts purchases by date and slides a window (30 days by default) across them. If a window contains two or more purchases that are each below the threshold (EUR 50,000 by default) and add up to at least the threshold, it is reported. Clusters never overlap, so one pattern produces one flag. Both values are configurable with `--threshold` and `--window`. The thresholds are illustrative: real limits depend on the jurisdiction and the type of contract.

**Unusual purchases.** For each category, the upper fence is `Q3 + k × IQR` (Tukey's fences, with `k = 3` by default). I chose quartiles over mean and standard deviation because a handful of extreme values inflate the standard deviation and can hide themselves; quartiles are not distorted that way. Categories with fewer than eight records are skipped, since quartiles from a tiny sample are unreliable.

A flag is a prompt for a person to look closer, not evidence of wrongdoing. There are legitimate reasons for clustered or large purchases.

## CSV format

```text
id,date,department,supplier,category,amount_eur,processing_days
1,2024-01-01,IT,Liffey Consulting Group,Office Supplies,175.96,7
```

Dates must be ISO format (`YYYY-MM-DD`). Amounts and processing days must not be negative. Errors name the offending line, for example `error: line 3: amount and processing days must be >= 0`.

## Project structure

```text
procureiq/
├── src/procureiq/
│   ├── cli.py         # argparse commands and table formatting
│   ├── db.py          # SQLite schema and validated CSV import
│   ├── analytics.py   # SQL reports and red-flag detection
│   └── generate.py    # deterministic synthetic data
├── tests/             # 28 unit tests (unittest)
├── data/              # sample dataset (synthetic)
└── .github/workflows/ci.yml
```

## Testing

```bash
python -m unittest discover -s tests -v
```

The suite covers CSV validation (including atomic loading), every report, edge cases for both detectors (clusters outside the window, different suppliers, departments and categories, purchases above the threshold, tiny categories, empty data), the generator's determinism, and the command-line interface. GitHub Actions runs it on Python 3.10, 3.11 and 3.12 for every push.

## Design decisions

- **SQLite as the engine.** Aggregations are expressed in SQL, which keeps the Python code short and shows how the data model maps to queries. The database lives in memory per run, so there is nothing to set up or clean up.
- **Detectors return dataclasses, not strings.** Analytics code knows nothing about formatting, so the same functions power both the table and JSON outputs and are easy to test.
- **All-or-nothing import.** A bad row aborts the load before anything is written, so the database never holds half a dataset.

## Roadmap

- Export reports to CSV and Excel.
- Persistent database file for large datasets.
- Supplier concentration metrics (for example, a Herfindahl–Hirschman index).
- A web dashboard on top of the same analytics (see my companion project, `spend-dashboard`).

## Author

Julliany Barbosa · [LinkedIn](https://www.linkedin.com/in/julliany-santos-barbosa) · [GitHub](https://github.com/jullianysantosbarbosa-code)

Released under the [MIT License](LICENSE).
