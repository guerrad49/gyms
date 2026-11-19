# Installation

## Requirements

- **Python 3.10 or newer** (tested on 3.10 to 3.14).
- **Tesseract**, the OCR program. It is a separate program, not a Python
  package.

Install Tesseract first:

```bash
# macOS (Homebrew)
brew install tesseract

# Debian / Ubuntu
sudo apt install tesseract-ocr
```

## Install the tool

Clone the repository, create a virtual environment, and install it with the
Google Sheets extra if you want to use a Google Sheet:

```bash
git clone <repository-url> pogo
cd pogo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[sheets]"
```

Leave out `[sheets]` if you will only use CSV or SQLite.

This puts a `pogo` command on your path while the virtual environment is
active. Check it:

```bash
pogo --version
pogo doctor
```

`pogo doctor` checks Python, Tesseract, your settings, the database and the
folders, and lists every problem in one run. Run it whenever something
seems wrong.

:::{note}
Remember to run `source .venv/bin/activate` in each new terminal before
using `pogo`.
:::
