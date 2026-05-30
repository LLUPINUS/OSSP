"""youtube_search 포맷터 단위 테스트 (네트워크 불필요)."""
from api.youtube_search import _format_duration, _format_view_count


class TestFormatDuration:
    def test_minutes_seconds(self):
        assert _format_duration("PT12M34S") == "12:34"

    def test_seconds_only(self):
        assert _format_duration("PT45S") == "0:45"

    def test_with_hours(self):
        assert _format_duration("PT1H2M3S") == "1:02:03"

    def test_minutes_only(self):
        assert _format_duration("PT5M") == "5:00"

    def test_pads_seconds(self):
        assert _format_duration("PT5M3S") == "5:03"

    def test_none(self):
        assert _format_duration(None) is None

    def test_empty(self):
        assert _format_duration("") is None

    def test_unparseable(self):
        # 라이브 방송 등 'P0D'는 형식 불일치 → None (UI에서 배지 생략)
        assert _format_duration("P0D") is None


class TestFormatViewCount:
    def test_under_ten_thousand(self):
        assert _format_view_count("1234") == "1,234회"

    def test_man_with_decimal(self):
        assert _format_view_count("12345") == "1.2만회"

    def test_man_exact_drops_decimal(self):
        assert _format_view_count("10000") == "1만회"

    def test_man_ten_or_more_is_integer(self):
        assert _format_view_count("123456") == "12만회"

    def test_man_large_with_separator(self):
        assert _format_view_count("12345678") == "1,234만회"

    def test_eok(self):
        assert _format_view_count("123456789") == "1.2억회"

    def test_none(self):
        assert _format_view_count(None) is None

    def test_empty(self):
        assert _format_view_count("") is None

    def test_non_numeric(self):
        assert _format_view_count("abc") is None
