class IndicatorRegistry:
    def register_indicator(self, name, cls):
        self._registry[name] = cls
