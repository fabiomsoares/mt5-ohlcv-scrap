# mt5-ohlcv-scrap
A simple scraping tool from MT5 to whatever destination

Scrapes OHLCV bars from a running MetaTrader 5 terminal, saves them as headerless
UTF-16 CSV files (MT5 export format) and uploads them over SFTP. SFTP is the first
supported destination.

## Files
- `mt5_ohlcv_exporter.py` – the script
- `requirements.txt` – runtime dependencies (Wine/Windows Python)
- `requirements-dev.txt` – test dependencies (native `python3`)
- `run.sh.example` – Linux launcher template
- `scripts/setup_wine_python.sh` – one-time Wine Python setup
- `tests/` – mocked tests
- `.env.example` – list of supported environment variables

## Requirements
`MetaTrader5` is a **Windows-only** package. There are two separate Python setups:

| Purpose | Python | Where |
|---|---|---|
| Mocked tests | native Ubuntu `python3` / `pip3` | Linux |
| Real scraper | Windows Python installed inside Wine | Wine |

Ubuntu has `python3` / `pip3`, not `python` / `pip`.

### 1. Run the mocked tests (native Ubuntu, no MT5/Wine/SFTP needed)
```bash
sudo apt install python3 python3-pip
python3 -m pip install -r requirements-dev.txt
python3 -m pytest
```
(On newer Ubuntu use a venv: `python3 -m venv .venv && . .venv/bin/activate` first.)

### 2. Install Windows Python inside Wine (one time)
```bash
sudo apt install wine curl
./scripts/setup_wine_python.sh
```
This downloads Windows Python (default 3.11.9, override with `PYTHON_VERSION`)
into `C:\Python311` and installs `requirements.txt` with it
(override the path with `WINE_PYTHON_EXE`). Also install and start the MT5
terminal in Wine.

### 3. Run the scraper
```bash
cp run.sh.example run.sh && chmod +x run.sh   # edit the values
./run.sh
# or directly:
wine 'C:\Python311\python.exe' mt5_ohlcv_exporter.py
```
On Windows: `pip install -r requirements.txt` and `python mt5_ohlcv_exporter.py`.

### Troubleshooting
- `python: command not found` / `pip: command not found` on Ubuntu: use `python3` / `pip3`.
- `wine python` fails with "no application associated with the specified file":
  Wine has no `python` on its PATH. Install Windows Python with
  `scripts/setup_wine_python.sh` and call the full path
  (`wine 'C:\Python311\python.exe' ...`).
- `MetaTrader5 package is not available`: you ran the script with Ubuntu's
  `python3`; run it with the Wine Python instead.

## Configuration (environment variables)
Credentials are never stored in the code.

| Variable | Required | Default |
|---|---|---|
| `SFTP_PASSWORD` | yes | – |
| `SFTP_HOST` | no | `ftp.server.com` |
| `SFTP_USER` | no | `user` |
| `SFTP_PORT` | no | `22` |
| `SFTP_REMOTE_DIR` | no | `/home/user/server.com/path` |
| `LOCAL_MT5_DIR` | no | `/home/ubuntu/.wine/drive_c/users/ubuntu/Documents` (Linux) / `C:\users\ubuntu\Documents` (Windows/Wine) |

```bash
export SFTP_PASSWORD="sftp_password"
export SFTP_HOST="ftp.server.com"
export SFTP_USER="user"
export SFTP_PORT=22
export SFTP_REMOTE_DIR="/home/user/server.com/path"
```

## Usage
See "Run the scraper" above.

Symbols, timeframes (`M1, M5, M15, M30, H1, H4, Daily, Weekly, Monthly`) and the
number of bars are set at the top of `main()`. Files are named
`<SYMBOL><TIMEFRAME>_<YYYYmmddHHMMSS>.csv`.
