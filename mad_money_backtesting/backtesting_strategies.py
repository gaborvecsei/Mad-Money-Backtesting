from datetime import datetime
from typing import List

import backtesting

import mad_money_backtesting as mmb


class MadMoneyStrategy(backtesting.Strategy):
    def __init__(self, broker, data, params):
        # This is a list of dates when we should buy the stock
        self.buy_dates: List[datetime] = None

        # This is a list of dates when we should sell the stock - this is not from Cramer, but based on simple rules
        # e.g.: sell at the end of the day, sell 1 week later, etc.
        self.sell_dates: List[datetime] = None

        # Defines how much stock we should buy
        self.buy_size: int = None
        super().__init__(broker, data, params)

    def init(self):
        super().init()

    def next(self):
        super().next()
        
        current_date = mmb.pd_date_to_datetime(self.data.Date[-1])

        if current_date in self.buy_dates:
            self.buy(size=self.buy_size)

        if current_date in self.sell_dates:
            if self.position.size > 0:
                self.position.close(1.0)
