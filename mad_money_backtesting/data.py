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
    assert max_price
    return f"symbol=&airdate={date_str}&called=%25&industry=%25&sector=%25&segment=%25&pricelow=0&pricehigh={max_price}&sortby=symbol"


def _get_data_from_row_in_table(cols: list) -> dict:
    if len(cols) != 6:
        raise ValueError(f"There should be 6 items in a row, all I got was: {len(cols)} - {cols}")

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
            # Usually this is the first/last row
            continue
        row_data["date"] = date
        daily_data.append(row_data)

    return daily_data


def scrape_cramer_calls(from_date: Union[str, datetime.datetime],
                        to_date: Union[str, datetime.datetime] = None,
                        max_price: int = 1000,
                        request_timeout: int = 10) -> pd.DataFrame:
    all_data = []

    if to_date is None:
        to_date = datetime.datetime.now().replace(hour=0, minute=0, second=0)
    dates_to_scrape = pd.bdate_range(from_date, to_date)

    pbar = tqdm(total=len(dates_to_scrape), desc="Scraping dates from Mad Money...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=None) as executor:
        futures = {}

        for date in dates_to_scrape:
            f = executor.submit(_download_data_for_date, date=date, max_price=max_price, timeout=request_timeout)
            futures[f] = date

        for f in concurrent.futures.as_completed(futures):
            date = futures[f]
            try:
                data = f.result()
                all_data.extend(data)
            except Exception as e:
                # print(f"Date failed: {date} - {e}")
                pass

            pbar.update(1)
    pbar.close()

    df = pd.DataFrame(all_data)
    return df


def transform_cramer_call_raw_dataframe(*, df: pd.DataFrame = None, file_path: Union[Path, str] = None) -> pd.DataFrame:
    if file_path:
        df = pd.read_csv(file_path)

    if df is None:
        raise ValueError("Either df ot file_path to a csv file should be given")

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    df = df.reset_index(drop=True)

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

    return df


def load_csv_for_backtesting(file_path: Union[Path, str], after_date: [str, datetime.datetime] = None):
    file_path = Path(file_path)
    df = pd.read_csv(file_path, parse_dates=["date"])
    if after_date:
        df = df[df["full_date"] > pd.to_datetime(after_date)]
    df = df[df["call"] == "buy"]
    return df
