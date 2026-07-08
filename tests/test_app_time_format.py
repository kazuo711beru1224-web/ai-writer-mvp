import datetime
import zoneinfo

import app


def test_fmt_mtime_converts_utc_epoch_to_jst_display():
    # UTC 2026-07-08 03:21:37 は日本時間で 2026-07-08 12:21:37 になる
    utc_dt = datetime.datetime(2026, 7, 8, 3, 21, 37, tzinfo=zoneinfo.ZoneInfo("UTC"))
    epoch_seconds = utc_dt.timestamp()

    assert app._fmt_mtime(epoch_seconds) == "2026-07-08 12:21:37"
