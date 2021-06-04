from copy import deepcopy
from datetime import datetime, timedelta
from typing import List, Tuple

import backtesting
import pandas as pd
import pytz

import mad_money_backtesting as mmb

# TODO: the TZ handling is pretty bad here - that needs a refactoring, it's 100%


class _BaseMadMoneyStrategy(backtesting.Strategy):

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

        # self.available_trade_dates: pd.Series = self.data.df["Date"]
        # self.available_trade_days: pd.Series = self.data.df.groupby(pd.Grouper(key="Date",
        #                                                                        freq="D")).first().reset_index()["Date"]

        buy_dates, sell_dates = self._calculate_buy_sell_dates(self.recommendation_dates)

        buy_dates = self._localize_dates(buy_dates)
        self.buy_dates = self._fix_non_existent_dates(buy_dates, mode="next_date")

        sell_dates = self._localize_dates(sell_dates)
        self.sell_dates = self._fix_non_existent_dates(sell_dates, mode="next_date")

    def init(self):
        super().init()

    def _localize_dates(self, dates: list):
        tz_ny = pytz.timezone('America/New_York')
        return [tz_ny.localize(x) for x in dates]

    def _calculate_buy_sell_dates(self, recommendation_dates: list) -> Tuple[list, list]:
        buy_dates = []
        sell_dates = []
        return buy_dates, sell_dates

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


class _QuickBuySellStrategies(_BaseMadMoneyStrategy):

    def __init__(self, broker, data, params):
        super().__init__(broker, data, params)

    def _calc_buy_date(self, recommendation_date) -> datetime:
        raise NotImplementedError()

    def _calc_sell_date(self, buy_date) -> datetime:
        raise NotImplementedError()

    def _calculate_buy_sell_dates(self, recommendation_dates: list) -> Tuple[list, list]:
        buy_dates = [self._calc_buy_date(d) for d in recommendation_dates]
        sell_dates = [self._calc_sell_date(d) for d in buy_dates]
        return buy_dates, sell_dates


class AfterShowBuyNextDayCloseSell(_QuickBuySellStrategies):

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=15, minute=30)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=15, minute=30) + timedelta(days=1)


class AfterShowBuyNextDayOpenSell(_QuickBuySellStrategies):

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=15, minute=30)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=9, minute=30) + timedelta(days=1)


class NextDayOpenBuyNextDayCloseSell(_QuickBuySellStrategies):

    def _calc_buy_date(self, recommendation_date) -> datetime:
        return mmb.pd_date_to_datetime(recommendation_date, hour=9, minute=30) + timedelta(days=1)

    def _calc_sell_date(self, buy_date) -> datetime:
        return buy_date.replace(hour=15, minute=30)


class BuyAndHold(_BaseMadMoneyStrategy):

    def __init__(self, broker, data, params):
        # Number of days to close the long position
        # (if it's more than the available data, e.g. 100000, then it's a "pure" buy and hold)
        self.sell_horizon: int = None
        super().__init__(broker, data, params)

    def _calculate_buy_sell_dates(self, recommendation_dates: list) -> Tuple[list, list]:
        buy_dates, sell_dates = [], []
        # offset = pd.tseries.offsets.BDay(self.sell_horizon)
        offset = timedelta(days=self.sell_horizon)

        for recomm in recommendation_dates:
            buy = mmb.pd_date_to_datetime(recomm, hour=15, minute=30)
            buy_dates.append(buy)

        # We do not want to buy more until we sell in the defined time horizon
        buy_dates = self._drop_dates_based_on_elapsed_time(buy_dates, timedelta(days=self.sell_horizon))

        for buy in buy_dates:
            sell = buy.replace(hour=15, minute=30) + offset
            sell_dates.append(sell)

        return buy_dates, sell_dates

    def _drop_dates_based_on_elapsed_time(self, dates, elapsed_time: timedelta) -> list:
        # The end result only makes sense if dates are sorted ascending (if i is the present, then i+1 is the future)
        # Example: input: dates=[1, 3, 4, 12, 15, 36, 34], elapsed=10 --> new_dates=[1, 12, 36]

        current_index = 0
        indices_to_remove = []

        while True:
            for k in range(current_index + 1, len(dates)):
                if (dates[k] - dates[current_index]) < elapsed_time:
                    indices_to_remove.append(k)

            current_index += 1

            if len(indices_to_remove) > 0:
                if current_index < (max(indices_to_remove) + 1):
                    current_index = max(indices_to_remove) + 1

            if current_index >= len(dates):
                break

        new_date_list = deepcopy(dates)
        for i in indices_to_remove:
            new_date_list.remove(dates[i])

        return new_date_list
