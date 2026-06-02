from trading.backtest_config import SLIPPAGE, FILL_MODEL

def run_backtest(strategy):
    return {"slippage": SLIPPAGE, "fill": FILL_MODEL}
