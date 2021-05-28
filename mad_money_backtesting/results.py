from typing import List

import pandas as pd


def summarize_backtesting_results(results: List[pd.Series],
                                  symbols: List[str],
                                  include_parameters: bool = True,
                                  sort_by: str = None) -> pd.DataFrame:
    results_df = pd.DataFrame(results)
    results_df = results_df[
        ["_strategy", "Return [%]", "Equity Final [$]", "Equity Peak [$]", "Buy & Hold Return [%]", "Start", "End"]]

    simplified_strategy_names = []
    strategy_parameters = []

    for i, strat_name in enumerate(results_df["_strategy"].values):
        strat_name = str(strat_name)
        name, parameters = strat_name.split("(")
        parameters = "(" + parameters
        simplified_strategy_names.append(name)
        strategy_parameters.append(parameters)

    if symbols is not None:
        if len(symbols) != len(results_df):
            raise ValueError("The number of symbols is not matching the number of rows in the df")
        results_df["Symbol"] = symbols

    results_df["Strategy"] = simplified_strategy_names
    if include_parameters:
        results_df["Parameters"] = strategy_parameters

    results_df.drop(columns="_strategy", inplace=True)
    results_df.set_index("Symbol", inplace=True)

    if sort_by is not None:
        results_df.sort_values(sort_by, inplace=True, ascending=False)

    return results_df

# For visualization: results_df.style.background_gradient(cmap="magma_r")
