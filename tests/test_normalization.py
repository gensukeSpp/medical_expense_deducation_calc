from app.normalization import parse_amount, parse_date


def test_parse_amount_numeric():
    assert parse_amount('3,800円') == 3800
    assert parse_amount('４，５００円') == 4500


def test_parse_amount_kanji():
    assert parse_amount('一万二千円') == 12000
    assert parse_amount('二千円') == 2000


def test_parse_date_formats():
    assert parse_date('2026/01/15') == '2026-01-15'
    assert parse_date('2026年1月5日') == '2026-01-05'
    assert parse_date('1/5/26') == '2026-01-05'
    assert parse_date('20260105') == '2026-01-05'
