from copy import deepcopy
from datetime import datetime, timedelta
from typing import List

import backtesting
import pandas as pd
import pytz

import mad_money_backtesting as mmb

# TODO: the TZ handling is pretty bad here - that needs a refactoring, it's 100%


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
        self.buy_dates = self._localize_dates(self.buy_dates)
        self.buy_dates = self._fix_non_existent_dates(self.buy_dates, mode="next_date")

        self.sell_dates: List[datetime] = [self._calc_sell_date(x) for x in self.buy_dates]
        self.sell_dates = self._localize_dates(self.sell_dates)
        self.sell_dates = self._fix_non_existent_dates(self.sell_dates, mode="next_date")

    def init(self):
        super().init()

    def _localize_dates(self, dates: list):
        tz_ny = pytz.timezone('America/New_York')
        return [tz_ny.localize(x) for x in dates]

    def _calc_buy_date(self, recommendation_date) -> datetime:
        raise NotImplementedError()

    def _calc_sell_date(self, buy_date) -> datetime:
        raise NotImplementedError()

    def _fix_non_existent_dates(self, date_list: list, mode: str) -> list:
        assert mode in {"drop", "next_date"}, f"Mode {mode} not available"

        # Drop: The date will be removed
        # Next_Date: The closes date will be selected to the original buy/sell date

        problematic_date_indices = []

        for i, d in enumerate(date_list):
            if sum(self.data.df["Date"] == d) == 0:
                # Calculated date is not part of the data (this can happen because of wrong calculation
                # or because of missing data)
                problematic_date_indices.append(i)

        fixed_date_list = deepcopy(date_list)

        for i in problematic_date_indices:
            if mode == "drop":
                item_to_drop = date_list[i]
                fixed_date_list.remove(item_to_drop)
            elif mode == "next_date":
                greater_dates_than_bad_one = self.data.df["Date"][self.data.df["Date"] > date_list[i]]
                if len(greater_dates_than_bad_one) == 0:
                    # When we don't have greater close dates, then we can drop the date
                    fixed_date_list.remove(date_list[i])
                else:
                    closest_date = greater_dates_than_bad_one.values[0]
                    closest_date = mmb.pd_date_to_datetime(closest_date)
                    closest_date = self._localize_dates([closest_date])[0]
                    fixed_date_list[i] = closest_date
                    # print(f"Problem: {date_list[i]}, fixed to {closest_date}")
        return fixed_date_list

    def next(self):
        super().next()

        current_date = mmb.pd_date_to_datetime(self.data.Date[-1])
        current_date = self._localize_dates([current_date])[0]

        if current_date in self.buy_dates:
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
        return mmb.pd_date_to_datetime(recommendation_date, hour=15, minute=30)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=15, minute=30) + timedelta(days=1)


class AfterShowBuyNextDayOpenSell(BaseMadMoneyStrategy):

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=15, minute=30)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=9, minute=30) + timedelta(days=1)


class NextDayOpenBuyNextDayCloseSell(BaseMadMoneyStrategy):

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=9, minute=30) + timedelta(days=1)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=15, minute=30)


class BuyAtFirstMentionAfterShowAndHold(BaseMadMoneyStrategy):

    def __init__(self, broker, data, params):
        self.sell_horizon: int = None
        super().__init__(broker, data, params)

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=15, minute=30)

    def _calc_sell_date(self, buy_date) -> datetime:
        # timedelta is huge so we won't sell it, the backtesting will sell at the last day automatically
        sell_date = buy_date.replace(hour=15, minute=30) + pd.tseries.offsets.BDay(self.sell_horizon)
        return mmb.pd_date_to_datetime(sell_date)
