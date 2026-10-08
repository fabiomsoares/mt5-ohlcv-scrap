#!/usr/bin/env python3
"""
MT5 OHLCV Scraper and SFTP Uploader
Scrapes OHLCV rates from MetaTrader 5, saves them locally to Wine Documents,
and uploads the CSV files to the designated SFTP endpoint.
"""

import argparse
import datetime
import os
import sys
from pathlib import Path

import pandas as pd
import paramiko

# MetaTrader5 Python package (requires Windows environment / Wine Python)
try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

# ==============================================================================
# CONFIGURATION & ENVIRONMENT VARIABLES
# ==============================================================================
SFTP_HOST = os.environ.get("SFTP_HOST", "ftp.server.com")
SFTP_PORT = int(os.environ.get("SFTP_PORT", 22))
SFTP_USER = os.environ.get("SFTP_USER", "user")
SFTP_PASSWORD = os.environ.get("SFTP_PASSWORD")  # Set via environment variable

SFTP_REMOTE_DIR = os.environ.get("SFTP_REMOTE_DIR", "/home/user/server.com/path")

# Handles both Linux host path and Windows/Wine internal path
DEFAULT_LINUX_PATH = "/home/ubuntu/.wine/drive_c/users/ubuntu/Documents"
DEFAULT_WINE_PATH = "C:\\users\\ubuntu\\Documents"

if sys.platform == "win32":
    LOCAL_DOCS_DIR = Path(os.environ.get("LOCAL_MT5_DIR", DEFAULT_WINE_PATH))
else:
    LOCAL_DOCS_DIR = Path(os.environ.get("LOCAL_MT5_DIR", DEFAULT_LINUX_PATH))

TIMEFRAME_MAP = {
    "M1": getattr(mt5, "TIMEFRAME_M1", 1) if mt5 else 1,
    "M5": getattr(mt5, "TIMEFRAME_M5", 5) if mt5 else 5,
    "M15": getattr(mt5, "TIMEFRAME_M15", 15) if mt5 else 15,
    "M30": getattr(mt5, "TIMEFRAME_M30", 30) if mt5 else 30,
    "H1": getattr(mt5, "TIMEFRAME_H1", 16385) if mt5 else 16385,
    "H4": getattr(mt5, "TIMEFRAME_H4", 16388) if mt5 else 16388,
    "Daily": getattr(mt5, "TIMEFRAME_D1", 16408) if mt5 else 16408,
    "Weekly": getattr(mt5, "TIMEFRAME_W1", 32769) if mt5 else 32769,
    "Monthly": getattr(mt5, "TIMEFRAME_MN1", 49153) if mt5 else 49153,
}


# ==============================================================================
# CORE FUNCTIONS
# ==============================================================================
def init_mt5(terminal_path=None):
    """Initializes connection to the running MetaTrader 5 terminal."""
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package is not available. Please run this script with the Windows "
            "Python installed in Wine (e.g. wine 'C:\\Python311\\python.exe' mt5_ohlcv_exporter.py)."
        )

    init_kwargs = {}
    if terminal_path:
        init_kwargs["path"] = terminal_path

    if not mt5.initialize(**init_kwargs):
        err = mt5.last_error()
        raise RuntimeError(f"MetaTrader 5 initialization failed: {err}")

    terminal_info = mt5.terminal_info()
    print(f"Connected to MT5 Terminal: {terminal_info.name} (connected: {terminal_info.connected})")


def scrape_ohlcv(symbol: str, timeframe_str: str, num_bars: int = 50000) -> pd.DataFrame:
    """Scrapes OHLCV bars from MT5 and formats dates to standard MT5 format."""
    if timeframe_str not in TIMEFRAME_MAP:
        raise ValueError(f"Unsupported timeframe '{timeframe_str}'.")

    tf = TIMEFRAME_MAP[timeframe_str]

    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Failed to select symbol '{symbol}' in Market Watch.")

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, num_bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates returned for {symbol} ({timeframe_str}). Error: {mt5.last_error()}")

    df = pd.DataFrame(rates)
    dt_series = pd.to_datetime(df["time"], unit="s")

    if timeframe_str in ["Daily", "Weekly", "Monthly"]:
        df["Formatted_Date"] = dt_series.dt.strftime("%Y.%m.%d")
    else:
        df["Formatted_Date"] = dt_series.dt.strftime("%Y.%m.%d %H:%M")

    # Format: [DateTime, Open, High, Low, Close, TickVolume, Volume]
    return pd.DataFrame(
        {
            "DateTime": df["Formatted_Date"],
            "Open": df["open"],
            "High": df["high"],
            "Low": df["low"],
            "Close": df["close"],
            "TickVolume": df["tick_volume"],
            "Volume": df["real_volume"],
        }
    )


def save_csv(df: pd.DataFrame, symbol: str, timeframe_str: str, output_dir: Path) -> Path:
    """Saves DataFrame as headerless UTF-16 CSV matching standard MT5 exports."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_suffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    # '$' and other special characters are kept as MT5 symbol names allow them
    filename = f"{symbol}{timeframe_str}_{ts_suffix}.csv"
    file_path = output_dir / filename

    df.to_csv(file_path, index=False, header=False, encoding="utf-16", sep=",")
    print(f"Saved {len(df)} rows to {file_path}")
    return file_path


def _sftp_makedirs(sftp, remote_dir: str):
    """Changes into remote_dir, creating missing path components."""
    if remote_dir.startswith("/"):
        sftp.chdir("/")
    for part in [p for p in remote_dir.split("/") if p]:
        try:
            sftp.chdir(part)
        except IOError:
            sftp.mkdir(part)
            sftp.chdir(part)


def upload_to_sftp(local_file: Path, remote_dir: str):
    """Uploads a local CSV file to the SFTP server."""
    if not SFTP_PASSWORD:
        raise ValueError("SFTP_PASSWORD environment variable is not set!")

    print(f"Connecting to SFTP server {SFTP_HOST}:{SFTP_PORT} as '{SFTP_USER}'...")
    transport = paramiko.Transport((SFTP_HOST, SFTP_PORT))
    sftp = None
    try:
        transport.connect(username=SFTP_USER, password=SFTP_PASSWORD)
        sftp = paramiko.SFTPClient.from_transport(transport)
        _sftp_makedirs(sftp, remote_dir)

        remote_target = f"{remote_dir.rstrip('/')}/{local_file.name}"
        print(f"Uploading {local_file.name} -> {remote_target}...")
        sftp.put(str(local_file), remote_target)
        print("Upload completed successfully.")
    finally:
        if sftp is not None:
            sftp.close()
        transport.close()


def show_account():
    """Prints the account the terminal is connected to (read-only). Returns True on success."""
    info = mt5.account_info()
    if info is None:
        print(f"No account information available; terminal not connected? Error: {mt5.last_error()}")
        return False
    print("Connected MT5 account:")
    print(f"  login:   {info.login}")
    print(f"  server:  {info.server}")
    print(f"  company: {info.company}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="MT5 OHLCV scraper and SFTP uploader")
    parser.add_argument(
        "--show-account",
        action="store_true",
        help="print the connected account (login, server, company) and exit without scraping",
    )
    args = parser.parse_args(argv or [])

    if args.show_account:
        try:
            init_mt5()
        except Exception as e:
            print(f"Initialization error: {e}")
            sys.exit(1)
        try:
            ok = show_account()
        finally:
            mt5.shutdown()
        sys.exit(0 if ok else 1)

    # Configure symbols and timeframes as needed
    symbols = ["WIN$N", "WDO$N", "EURUSD"]
    timeframes = ["M1"]
    num_bars = 50000

    print("=== MT5 OHLCV Scraper & SFTP Uploader ===")
    print(f"Local output directory: {LOCAL_DOCS_DIR}")
    print(f"Remote SFTP target: {SFTP_USER}@{SFTP_HOST}:{SFTP_REMOTE_DIR}")

    try:
        init_mt5()
    except Exception as e:
        print(f"Initialization error: {e}")
        sys.exit(1)

    exported_files = []
    try:
        for sym in symbols:
            for tf in timeframes:
                print(f"\nScraping {sym} [{tf}]...")
                try:
                    df = scrape_ohlcv(sym, tf, num_bars=num_bars)
                    csv_path = save_csv(df, sym, tf, LOCAL_DOCS_DIR)
                    exported_files.append(csv_path)
                except Exception as e:
                    print(f"Error processing {sym} {tf}: {e}")

        if exported_files:
            print(f"\n--- Uploading {len(exported_files)} file(s) via SFTP ---")
            for csv_file in exported_files:
                upload_to_sftp(csv_file, SFTP_REMOTE_DIR)
            print("\nExport and upload process finished.")
        else:
            print("No files were exported.")
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main(sys.argv[1:])
