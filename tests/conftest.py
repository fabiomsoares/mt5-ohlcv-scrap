import sys
import types
from unittest import mock

import pytest

# Mock MetaTrader5 and paramiko before the exporter is imported.
_mt5 = mock.MagicMock(name="MetaTrader5")
for _n, _v in dict(TIMEFRAME_M1=1, TIMEFRAME_M5=5, TIMEFRAME_M15=15, TIMEFRAME_M30=30,
                   TIMEFRAME_H1=16385, TIMEFRAME_H4=16388, TIMEFRAME_D1=16408,
                   TIMEFRAME_W1=32769, TIMEFRAME_MN1=49153).items():
    setattr(_mt5, _n, _v)
sys.modules["MetaTrader5"] = _mt5
sys.modules["paramiko"] = mock.MagicMock(name="paramiko")

import mt5_ohlcv_exporter  # noqa: E402


@pytest.fixture
def exporter():
    mt5_ohlcv_exporter.mt5.reset_mock(return_value=True, side_effect=True)
    mt5_ohlcv_exporter.paramiko.reset_mock(return_value=True, side_effect=True)
    return mt5_ohlcv_exporter
