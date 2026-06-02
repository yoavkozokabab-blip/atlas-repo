from indicators.indicator_registry import IndicatorRegistry

class SignalRegistry(IndicatorRegistry):
    def register_signal(self, name, fn):
        return fn
