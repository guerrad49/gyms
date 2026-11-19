# Contributing

## Set up

```bash
git clone <repository-url> pogo && cd pogo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,docs,sheets]"
pre-commit install
```

You also need the Tesseract program (`brew install tesseract` on macOS).

## The checks

Everything below runs in CI and must pass:

```bash
ruff format . && ruff check .      # style and docstring rules
mypy                               # strict type checking
pytest --cov                       # tests; coverage must stay above 90%
sphinx-build -W -b html docs docs/_build/html   # the documentation
```

## Standards

- **80 columns** for all Python, including docstrings and comments.
- **Type hints everywhere**, checked with `mypy --strict`.
- **numpy-style docstrings** for every public module, class and function,
  with runnable examples where they help.
- Python **3.10** is the minimum: no `Self`, `StrEnum`, `tomllib`, or other
  3.11-only features.
- No `input()` or `print()` outside `cli.py`. Questions go through a
  `Prompter`, so everything can run unattended and be tested.

## Tests

- Tests marked `ocr` need Tesseract and are skipped without it.
- **No test may use the network.** A fixture makes any real connection fail;
  only a test marked `live` can opt out. Address lookups and Google Sheets
  are faked.
- The six screenshots in `tests/fixtures/images` have their correct values in
  `tests/fixtures/expected.json`. Don't add real gym data to the repository
  (coordinates reveal where someone has been); use small invented tables.
- Each storage backend must pass the shared contract tests in
  `tests/test_store_contract.py`.

## Adding things

- **A phone**: add a `DeviceProfile` to the table in
  `src/PokemonGo/vision/devices.py` (screen size, OCR scale, the rows of the
  title and statistics areas), and a fixture screenshot with its expected
  values.
- **A storage backend**: implement `GymStore` (`store/base.py`), add it to
  `open_store`, and add it to the contract tests.

## Commits and releases

Commit messages follow
[Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Effect |
|---|---|
| `feat:` | a new feature (minor version) |
| `fix:` | a bug fix (patch version) |
| `feat!:` or a `BREAKING CHANGE:` footer | a breaking change (major version) |
| `docs:`, `test:`, `ci:`, `build:`, `refactor:`, `chore:` | no release on their own |

The version is never edited by hand. It comes from git tags (`vX.Y.Z`).
On every push to `main`, the release workflow keeps a **release pull
request** up to date with the next version number and the generated
`CHANGELOG.md`. Merging that pull request creates the tag and a GitHub
release, and the documentation is rebuilt.

The first release is pinned to `2.0.0` in `release-please-config.json`
(`"release-as"`). **Remove that line after the first release**, or every
later release would be forced to 2.0.0.

One-time repository settings:

- Settings, Pages, Source: **GitHub Actions**.
- Settings, Actions, General, Workflow permissions: allow GitHub Actions to
  **create and approve pull requests**.
- Enable secret scanning with push protection, and Dependabot.
