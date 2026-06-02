def test_sma():
    from indicators.sma import SMAIndicator
    assert SMAIndicator().compute([]) == []
