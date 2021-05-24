import argparse
from pathlib import Path

import mad_money_backtesting as mmb


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--from-date", type=str, default="2020-01-01",
                        help="The scraping will start at this date.")
    parser.add_argument("-t", "--to-date", type=str, default=None,
                        help="The scraping will end at this date. If not defined, then today will be used")
    parser.add_argument("-o", "--output", type=str, default="mad_money.csv", help="Output file path")
    parser.add_argument("-p", "--max-price", type=int, default=1000)
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = get_args()

    output_path = Path(args.output)

    df = mmb.scrape_cramer_calls(args.from_date, args.to_date, args.max_price, request_timeout=10)
    df.to_csv(f"{output_path.stem}_RAW.csv", index=False)

    df = mmb.transform_cramer_call_raw_dataframe(df=df)
    df.to_csv(output_path, index=False)
