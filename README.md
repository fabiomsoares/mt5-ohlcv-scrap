# mt5-ohlcv-scrap
A simple scraping tool from MT5 to whatever destination

Scrapes OHLCV bars from a running MetaTrader 5 terminal, saves them as headerless
UTF-16 CSV files (MT5 export format) and uploads them over SFTP. SFTP is the first
supported destination.

## Files
- `mt5_ohlcv_exporter.py` – the script
- `requirements.txt` – Python dependencies
- `.env.example` – list of supported environment variables

## Requirements
MetaTrader 5 only runs on Windows, so on Linux use Wine with a Windows Python
that has the dependencies installed, and the MT5 terminal running.

```bash
# Windows
pip install -r requirements.txt
# Linux (Wine)
wine python -m pip install -r requirements.txt
```

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
```bash
wine python mt5_ohlcv_exporter.py   # Linux + Wine
python mt5_ohlcv_exporter.py        # Windows
```

Symbols, timeframes (`M1, M5, M15, M30, H1, H4, Daily, Weekly, Monthly`) and the
number of bars are set at the top of `main()`. Files are named
`<SYMBOL><TIMEFRAME>_<YYYYmmddHHMMSS>.csv`.
