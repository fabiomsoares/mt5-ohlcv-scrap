import numpy as np
import pytest
from unittest import mock


def make_rates(times):
    dt = np.dtype([("time", "i8"), ("open", "f8"), ("high", "f8"), ("low", "f8"),
                   ("close", "f8"), ("tick_volume", "i8"), ("spread", "i4"),
                   ("real_volume", "i8")])
    return np.array([(t, 1.0, 2.0, 0.5, 1.5, 10, 0, 100) for t in times], dtype=dt)


# 2024-01-02 03:04:00 UTC
TS = 1704164640


def test_init_mt5_success(exporter):
    exporter.mt5.initialize.return_value = True
    exporter.init_mt5()
    exporter.mt5.initialize.assert_called_once_with()


def test_init_mt5_with_path(exporter):
    exporter.mt5.initialize.return_value = True
    exporter.init_mt5("C:\\mt5\\terminal64.exe")
    exporter.mt5.initialize.assert_called_once_with(path="C:\\mt5\\terminal64.exe")


def test_init_mt5_failure(exporter):
    exporter.mt5.initialize.return_value = False
    exporter.mt5.last_error.return_value = (-1, "boom")
    with pytest.raises(RuntimeError, match="initialization failed"):
        exporter.init_mt5()


def test_scrape_intraday_format(exporter):
    exporter.mt5.symbol_select.return_value = True
    exporter.mt5.copy_rates_from_pos.return_value = make_rates([TS])
    df = exporter.scrape_ohlcv("EURUSD", "M1", 10)
    assert list(df.columns) == ["DateTime", "Open", "High", "Low", "Close", "TickVolume", "Volume"]
    assert df["DateTime"].iloc[0] == "2024.01.02 03:04"
    exporter.mt5.copy_rates_from_pos.assert_called_once_with("EURUSD", 1, 0, 10)


def test_scrape_daily_format(exporter):
    exporter.mt5.symbol_select.return_value = True
    exporter.mt5.copy_rates_from_pos.return_value = make_rates([TS])
    df = exporter.scrape_ohlcv("EURUSD", "Daily", 10)
    assert df["DateTime"].iloc[0] == "2024.01.02"


def test_unsupported_timeframe(exporter):
    with pytest.raises(ValueError, match="Unsupported timeframe"):
        exporter.scrape_ohlcv("EURUSD", "M7")


def test_symbol_select_failure(exporter):
    exporter.mt5.symbol_select.return_value = False
    with pytest.raises(RuntimeError, match="Failed to select symbol"):
        exporter.scrape_ohlcv("BAD", "M1")


def test_no_rates(exporter):
    exporter.mt5.symbol_select.return_value = True
    exporter.mt5.copy_rates_from_pos.return_value = None
    exporter.mt5.last_error.return_value = (1, "none")
    with pytest.raises(RuntimeError, match="No rates returned"):
        exporter.scrape_ohlcv("EURUSD", "M1")


def test_save_csv(exporter, tmp_path):
    exporter.mt5.symbol_select.return_value = True
    exporter.mt5.copy_rates_from_pos.return_value = make_rates([TS])
    df = exporter.scrape_ohlcv("EURUSD", "M1")
    out = tmp_path / "sub"
    path = exporter.save_csv(df, "WIN$N", "M1", out)
    assert path.parent == out
    assert path.name.startswith("WIN$NM1_") and path.suffix == ".csv"
    text = path.read_bytes().decode("utf-16")
    assert text.splitlines()[0].startswith("2024.01.02 03:04,1.0,2.0,0.5,1.5,10,100")
    assert "DateTime" not in text


def test_sftp_makedirs_creates_missing(exporter):
    sftp = mock.MagicMock()
    sftp.chdir.side_effect = [None, None, IOError(), None, IOError(), None]
    exporter._sftp_makedirs(sftp, "/a/b/c")
    assert [c.args[0] for c in sftp.mkdir.call_args_list] == ["b", "c"]


def test_upload_requires_password(exporter, monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "SFTP_PASSWORD", None)
    with pytest.raises(ValueError):
        exporter.upload_to_sftp(tmp_path / "x.csv", "/r")


def test_upload_to_sftp(exporter, monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "SFTP_PASSWORD", "pw")
    f = tmp_path / "x.csv"
    f.write_text("a")
    transport = exporter.paramiko.Transport.return_value
    sftp = exporter.paramiko.SFTPClient.from_transport.return_value
    exporter.upload_to_sftp(f, "/remote/dir/")
    sftp.put.assert_called_once_with(str(f), "/remote/dir/x.csv")
    sftp.close.assert_called_once()
    transport.close.assert_called_once()


def test_main_happy_path(exporter, monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "LOCAL_DOCS_DIR", tmp_path)
    monkeypatch.setattr(exporter, "init_mt5", lambda: None)
    monkeypatch.setattr(exporter, "scrape_ohlcv", lambda *a, **k: exporter.pd.DataFrame({"a": [1]}))
    upload = mock.Mock()
    monkeypatch.setattr(exporter, "upload_to_sftp", upload)
    exporter.main()
    assert upload.call_count == 3
    exporter.mt5.shutdown.assert_called_once()


def test_main_partial_failure(exporter, monkeypatch, tmp_path):
    monkeypatch.setattr(exporter, "LOCAL_DOCS_DIR", tmp_path)
    monkeypatch.setattr(exporter, "init_mt5", lambda: None)

    def scrape(sym, tf, num_bars=0):
        if sym == "WDO$N":
            raise RuntimeError("fail")
        return exporter.pd.DataFrame({"a": [1]})

    monkeypatch.setattr(exporter, "scrape_ohlcv", scrape)
    upload = mock.Mock()
    monkeypatch.setattr(exporter, "upload_to_sftp", upload)
    exporter.main()
    assert upload.call_count == 2
    exporter.mt5.shutdown.assert_called_once()


def test_main_init_failure_exits(exporter, monkeypatch):
    def boom():
        raise RuntimeError("x")

    monkeypatch.setattr(exporter, "init_mt5", boom)
    with pytest.raises(SystemExit) as e:
        exporter.main()
    assert e.value.code == 1


def test_show_account_success(exporter, monkeypatch, capsys):
    monkeypatch.setattr(exporter, "init_mt5", lambda: None)
    exporter.mt5.account_info.return_value = mock.Mock(login=123, server="Broker-Live", company="Broker Ltd")
    scrape, save, upload = mock.Mock(), mock.Mock(), mock.Mock()
    monkeypatch.setattr(exporter, "scrape_ohlcv", scrape)
    monkeypatch.setattr(exporter, "save_csv", save)
    monkeypatch.setattr(exporter, "upload_to_sftp", upload)
    with pytest.raises(SystemExit) as e:
        exporter.main(["--show-account"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert "123" in out and "Broker-Live" in out and "Broker Ltd" in out
    scrape.assert_not_called()
    save.assert_not_called()
    upload.assert_not_called()
    exporter.mt5.shutdown.assert_called_once()


def test_show_account_no_info(exporter, monkeypatch, capsys):
    monkeypatch.setattr(exporter, "init_mt5", lambda: None)
    exporter.mt5.account_info.return_value = None
    with pytest.raises(SystemExit) as e:
        exporter.main(["--show-account"])
    assert e.value.code == 1
    assert "No account information" in capsys.readouterr().out
    exporter.mt5.shutdown.assert_called_once()


def test_show_account_init_failure(exporter, monkeypatch):
    def boom():
        raise RuntimeError("x")

    monkeypatch.setattr(exporter, "init_mt5", boom)
    with pytest.raises(SystemExit) as e:
        exporter.main(["--show-account"])
    assert e.value.code == 1
