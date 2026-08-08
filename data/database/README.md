# Decision OS Databases

This directory intentionally mixes Git-managed research databases and one local-only working database.

| File | Policy | Purpose |
|---|---|---|
| `master.db` | Git-managed | Universe, securities, themes, framework/model/routine metadata |
| `history.db` | Git-managed | Candidate, decision, portfolio/capital, outcome and review history |
| `analysis.db` | local-only | High-volume market observations, order book, intraday features and cache |
| `investment_lab.sqlite` | local-only | SBI execution history and derived trade-analysis tables; raw brokerage data is not committed |

The checked-in `master.db` and `history.db` may begin as empty SQLite placeholders. Run migrations before use:

```bash
python scripts/init_decision_os_db.py --target master
python scripts/init_decision_os_db.py --target history
```

Or initialize all databases including the local analysis database:

```bash
python scripts/init_decision_os_db.py
```

After research data is added or migrations alter `master.db` / `history.db`, commit those two DB files together with the Markdown, migration, journal or other source changes that explain why the research state changed.

Never force-add `analysis.db`. It is intentionally reproducible/local working data and can grow quickly.
