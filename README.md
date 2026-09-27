# Kaggle Notebook Version Downloader

Download every saved version of a Kaggle notebook as an `.ipynb` file using Selenium and an existing signed-in Chromium session.

## Requirements

- Python 3
- Chromium or Google Chrome
- A Kaggle account with access to the notebook

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install selenium
```

Set the notebook URL near the top of `download.py`:

```python
NOTEBOOK_URL = "https://www.kaggle.com/code/YOUR_USERNAME/NOTEBOOK_NAME"
```

Optionally change the destination:

```python
DOWNLOAD_DIR = os.path.expanduser("~/Downloads/kaggle_versions")
```

## Run

Start Chromium with remote debugging:

```bash
chromium --remote-debugging-port=9222 \
  --user-data-dir="$PWD/selenium-chrome-profile"
```

Sign in to Kaggle in that browser, then run:

```bash
./venv/bin/python download.py
```

Keep Chromium open until the script finishes.

## Output

The script opens Version History, selects each version, and downloads `Download .ipynb`. Files are renamed to include their version so they are not overwritten:

```text
24f2001127-notebook-2026t2_Version_64.ipynb
24f2001127-notebook-2026t2_Version_63.ipynb
```

Each version is retried up to three times. Any versions that still fail are listed when the run finishes.
<img width="954" height="478" alt="image" src="https://github.com/user-attachments/assets/ec56b812-7997-4d88-b865-262c29f1e29b" />


## Troubleshooting

- `cannot connect to chrome`: confirm Chromium is running with `--remote-debugging-port=9222`.
- Kaggle login errors: sign in manually in the remote-debugging browser before starting the script.
- Download timeout: check that `DOWNLOAD_DIR` exists and that Chromium can write to it.
- Port already in use: close the old remote-debugging browser before starting another one.
