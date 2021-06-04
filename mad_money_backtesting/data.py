import concurrent.futures
import datetime
import re
from pathlib import Path
from typing import Union

import pandas as pd
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

URL = "https://madmoney.thestreet.com/screener/index.cfm?showview=stocks&showrows=500"
HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}


def _create_form_input(date_str: str, max_price: int = 1000):
    assert len(date_str.split("-")) == 3, "Date should be formatted as YYYY-MM-DD"
    assert 0 < max_price <= 1000, "Max price should be in range [0, 1000]"
    return f"symbol=&airdate={date_str}&called=%25&industry=%25&sector=%25&segment=%25&pricelow=0&pricehigh={max_price}&sortby=symbol"


class WrongNumberOfItemsInRow(ValueError):
    pass


class NoDataForDateException(RuntimeError):
    pass


def _get_data_from_row_in_table(cols: list) -> dict:
    if len(cols) != 6:
        raise WrongNumberOfItemsInRow(f"There should be 6 items in a row, all I got was: {len(cols)} - {cols}")

    name = cols[0].text
    date = cols[1].text
    segment_type = cols[2].find("img")["alt"]
    call_type = cols[3].find("img")["alt"]
    current_price = cols[4].text

    return {"name": name,
            "month_and_day": date,
            "segment": segment_type,
            "call": call_type,
            "current_price": current_price}


def _download_data_for_date(date: Union[str, datetime.datetime], max_price: int, timeout: int):
    date_format = "%Y-%m-%d"
    if not isinstance(date, str):
        date = date.strftime(date_format)
    else:
        date = pd.to_datetime(date).strftime(date_format)

    page = requests.post(url=URL, headers=HEADERS, data=_create_form_input(date, max_price), timeout=timeout)
    soup = BeautifulSoup(page.text, features="lxml")

    stock_table = soup.find("table", attrs={"id": "stockTable"})
    stock_table_rows = stock_table.find_all("tr")

    daily_data = []

    for row in stock_table_rows:
        cols_in_table = row.find_all("td")

        try:
            row_data = _get_data_from_row_in_table(cols_in_table)
        except ValueError:
            # This happens when there is not data in one of the rows in the table
            # Usually this is the first/last row so totally normal no need to panic
            continue
        row_data["date"] = date
        daily_data.append(row_data)

    if len(daily_data) == 0:
        # If there is no data for a day, it's fine (no show on weekends) but we should
        # still notify the user that there was no data for the requested date
        # There is no exception raised before as when there is no data, there is still a table on the site
        raise NoDataForDateException(f"There was no data for: {date}")

    return daily_data


def scrape_cramer_calls(from_date: Union[str, datetime.datetime],
                        to_date: Union[str, datetime.datetime] = None,
                        max_price: int = 1000,
                        request_timeout: int = 10) -> pd.DataFrame:
    all_data = []

    if to_date is None:
        to_date = datetime.datetime.now().replace(hour=0, minute=0, second=0)
    dates_to_scrape = list(pd.bdate_range(from_date, to_date))

    pbar = tqdm(total=len(dates_to_scrape), desc="Scraping dates from Mad Money...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        while len(dates_to_scrape) > 0:
            completed_dates = []
            futures = {}

            for date in dates_to_scrape:
                f = executor.submit(_download_data_for_date, date=date, max_price=max_price, timeout=request_timeout)
                futures[f] = date

            for f in concurrent.futures.as_completed(futures):
                date = futures[f]
                try:
                    data = f.result()
                    all_data.extend(data)
                    completed_dates.append(date)
                    pbar.update(1)
                except NoDataForDateException:
                    print(f"There is no data for the date: {date}. Maybe there was no show, or the data is not recorded yet on their website")
                    completed_dates.append(date)
                    pbar.update(1)
                except Exception as e:
                    print(f"Date failed: {date} - {e}, will try again")

            _ = [dates_to_scrape.remove(d) for d in completed_dates]

    pbar.close()

    df = pd.DataFrame(all_data)
    return df


def transform_cramer_call_raw_dataframe(*, df: pd.DataFrame = None, file_path: Union[Path, str] = None) -> pd.DataFrame:
    if file_path:
        df = pd.read_csv(file_path)

    if df is None:
        raise ValueError("Either df ot file_path to a csv file should be given")

    df["date"] = pd.to_datetime(df["date"])

    # Transform call values
    df["call"] = df["call"].astype(int)

    # Verbose call values
    call_dict = {1: "sell", 2: "negative", 3: "hold", 4: "positive", 5: "buy", 6: "I have no idea what is this"}
    df["call"] = df["call"].transform(lambda x: call_dict[x])

    # Convert price to number
    df["current_price"] = df["current_price"].replace(r"[\$,]", "", regex=True).astype(float)

    # Extract symbol
    pattern = r"\(([^\)]+)\)"
    df["symbol"] = df["name"].transform(lambda x: re.findall(pattern, x)[-1].upper())

    # Let's sort the dataframe on 2 levels: date and symbol
    df = df.sort_values(["date", "name"])
    df = df.reset_index(drop=True)

    return df
