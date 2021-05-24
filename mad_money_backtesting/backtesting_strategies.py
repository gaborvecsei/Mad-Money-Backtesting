from datetime import datetime, timedelta
from typing import List

import backtesting

import mad_money_backtesting as mmb


class BaseMadMoneyStrategy(backtesting.Strategy):
    def __init__(self, broker, data, params):
        # Cramer's buy recommendation dates for the stock
        self.recommendation_dates: List[datetime] = None

        # Stop loss - if None, there is no stop loss
        self.stop_loss_perc: float = None

        # Take profit - if None there is no take profit
        self.take_profit_perc: float = None

        super().__init__(broker, data, params)

        if len(self.recommendation_dates) == 0:
            raise RuntimeError("No recommendation dates are defined")
        self.buy_dates: List[datetime] = [self._calc_buy_date(x) for x in self.recommendation_dates]
        self.sell_dates: List[datetime] = [self._calc_sell_date(x) for x in self.buy_dates]

    def init(self):
        super().init()

    def _calc_buy_date(self, recommendation_date) -> datetime:
        raise NotImplementedError()

    def _calc_sell_date(self, buy_date) -> datetime:
        raise NotImplementedError()

    def next(self):
        super().next()

        current_date = mmb.pd_date_to_datetime(self.data.Date[-1])

        if current_date in self.buy_dates:
            # TODO: do we buy on Open or Close?
            current_close_value = self.data.Close[-1]
            stop_loss_value = None
            take_profit_value = None
            if self.stop_loss_perc:
                stop_loss_value = current_close_value - (current_close_value * self.stop_loss_perc)
            if self.take_profit_perc:
                take_profit_value = current_close_value + (current_close_value * self.take_profit_perc)

            self.buy(size=0.999, sl=stop_loss_value, tp=take_profit_value)

        if current_date in self.sell_dates:
            if self.position.size > 0:
                self.position.close(1.0)


class AfterShowBuyNextDayCloseSell(BaseMadMoneyStrategy):
    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=16, minute=0)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=16, minute=0) + timedelta(days=1)


class AfterShowBuyNextDayOpenSell(BaseMadMoneyStrategy):
    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=16, minute=0)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=9, minute=30) + timedelta(days=1)


class NextDayOpenBuyNextDayCloseSell(BaseMadMoneyStrategy):
    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=9, minute=30) + timedelta(days=1)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=16, minute=0)
