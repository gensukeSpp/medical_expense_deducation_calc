from app.normalization import parse_amount, parse_date


def test_parse_amount_numeric():
    assert parse_amount("3,800円") == 3800
    assert parse_amount("４，５００円") == 4500


def test_parse_amount_kanji():
    assert parse_amount("一万二千円") == 12000
    assert parse_amount("二千円") == 2000


def test_parse_amount_plain_number():
    """テスト: プレーンな数字文字列が正しくパースされる"""
    assert parse_amount("3800") == 3800
    assert parse_amount("3,800") == 3800
    assert parse_amount("12345") == 12345
    assert parse_amount("0") == 0


def test_parse_amount_empty_string():
    """テスト: 空文字列は None を返す"""
    assert parse_amount("") is None
    assert parse_amount("   ") is None


def test_parse_amount_non_numeric_string():
    """テスト: 非数字文字列は None を返す（既存動作の維持）"""
    assert parse_amount("abc") is None
    assert parse_amount("3800円abc") == 3800  # 純粋な数字のマッチを許容
    assert parse_amount("3800円と500円") == 3800  # 複数の金額表現があった場合は最初の数字のみ


def test_parse_amount_existing_formats_unchanged():
    """テスト: 既存の日本語形式の動作が変わらない"""
    assert parse_amount("3800円") == 3800
    assert parse_amount("2000") == 2000  # プレーン数字
    assert parse_amount("一万二千円") == 12000
