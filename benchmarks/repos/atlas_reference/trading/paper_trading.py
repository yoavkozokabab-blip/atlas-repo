from trading.paper_config import SLIPPAGE, FILL_MODEL
from trading.backtest_engine import run_backtest

def run_paper(strategy):
    return {"slippage": SLIPPAGE, "fill": FILL_MODEL}
