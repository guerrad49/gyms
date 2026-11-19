# Troubleshooting

Start with:

```bash
pogo doctor
```

It checks the whole setup and tells you what to fix.

| Message or symptom | What to do |
|---|---|
| `tesseract not found` | Install Tesseract (`brew install tesseract` on macOS, `sudo apt install tesseract-ocr` on Debian or Ubuntu). |
| `this database uses the old layout ... run 'pogo upgrade'` | Run `pogo upgrade --dry-run`, then `pogo upgrade`. See [](database.md). |
| `EMAIL must be a valid contact address` | Set `EMAIL` in `variables.env`. Nominatim requires you to identify yourself. |
| `image size 1000x2000 matches no known phone; the closest profile is ... (force it with --model ...)` | Your screenshots are a size the tool does not know. Try `--model i15` (or `i11`, `iSE`); the crops are scaled to fit. |
| `Google Sheets request failed (403)` or `cannot open spreadsheet` | Share the spreadsheet with the service account's `client_email` as an Editor, and check `SHEET_NAME` and `JSON_KEY`. |
| `Google Sheets request failed (429)` | You used the per-minute quota. It is retried automatically; run again if it gave up. |
| `Google Sheets support is not installed` | `pip install -e ".[sheets]"`. |
| `address lookups were switched off after 3 failures` | The address service was unreachable. The gyms were saved with the `ADDRESS` flag; run `pogo resolve` later. |
| A screenshot was skipped | The summary says why. Run `pogo scan` again without `--non-interactive` to answer the questions. |
| `... already exists; not overwriting it` | A different file with that name is already in `badges/`. Move it away and rescan. |
| `already in the database as #N` | That screenshot was scanned before; nothing was added. |
| A title is slightly wrong | Run with `-v` to see what was read. Titles are matched loosely, so a seeded gym is still found. |
| Statistics were misread | Type them when asked, or fix the row by hand. Run `pogo eval` to check the reading against your data. |

## Getting more detail

`pogo scan -v` shows each title candidate and the reading variant that
produced it. For a single problem screenshot, scan just that file:

```bash
pogo scan IMG_1234.PNG --dry-run -v
```

If you report a problem, include the output of `pogo doctor` and
`pogo --version`.
