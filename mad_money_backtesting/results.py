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
        if symbols is not None:
            name = f"{name} ({symbols[i]})"
        parameters = "(" + parameters
        simplified_strategy_names.append(name)
        strategy_parameters.append(parameters)

    results_df["Strategy"] = simplified_strategy_names
    if include_parameters:
        results_df["Parameters"] = strategy_parameters
    results_df.drop(columns="_strategy", inplace=True)
    results_df.set_index("Strategy", inplace=True)

    if sort_by is not None:
        results_df.sort_values(sort_by, inplace=True, ascending=False)

    return results_df

# For visualization: results_df.style.background_gradient(cmap="magma_r")