# Using Google Sheets

A Google Sheet is a good database if you want to edit rows by hand, share
the data, or feed Google My Maps. It needs a one-time setup so the tool can
write to your sheet.

## 1. Install the extra

```bash
pip install -e ".[sheets]"
```

## 2. Create a service account

The tool signs in as a *service account*, a robot user that belongs to a
Google Cloud project. Follow the **service account** instructions in the
[gspread authentication guide](https://docs.gspread.org/en/latest/oauth2.html).
In short:

1. Create a Google Cloud project and enable the **Google Sheets API** and
   the **Google Drive API**.
2. Create a service account and download its **JSON key**.
3. Save the key next to your settings file. Do not commit it.

## 3. Create and share the spreadsheet

Create a spreadsheet and open the JSON key. Copy the `client_email` value
(it looks like `name@project.iam.gserviceaccount.com`) and **share the
spreadsheet with that address as an Editor**. Without this the tool cannot
see the sheet.

The database lives in the **first sheet** of the spreadsheet. An empty sheet
gets its header row on the first scan. If you already have a version 1
sheet, see [](migrating-from-v1.md).

## 4. Settings

```
EMAIL=you@example.com
BACKEND=sheets
SHEET_NAME=gym_data
JSON_KEY=my-project-key.json
```

`JSON_KEY` is relative to the folder holding `variables.env`. Then check it:

```bash
pogo doctor
```

## Good to know

- **Don't edit the sheet while a scan is running.** The tool reads the sheet
  once at the start and updates the rows it knows about.
- **Quotas.** Google limits how many writes you can make per minute. The tool
  commits after each screenshot, and retries with growing waits when Google
  says the quota is used up. A very large batch may simply take a little
  longer.
- **Formatted values.** The sheet is read as displayed. If you format the
  coordinate columns to show fewer decimals, they will be read rounded, and a
  locale that writes decimals with a comma will not parse. Keep those
  columns as plain numbers.
- **Sorting** moves rows, so the tool sorts only at the end of a scan.
- **Your own columns** to the right of the standard ones are never touched.
