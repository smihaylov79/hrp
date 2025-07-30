from urllib.parse import unquote

import pandas as pd


def deep_clean(obj):
    if isinstance(obj, dict):
        return {unquote(k): deep_clean(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [deep_clean(i) for i in obj]
    elif isinstance(obj, str):
        return unquote(obj)
    else:
        return obj


def create_dataframe(data):
    df = pd.DataFrame(data)
    df = df.rename(columns={0:'symbol', 1: 'company_name', 2: 'open', 3: 'previous_close', 4: 'isin', 5: 'path'})
    df['gap_open'] = df['open'] - df['previous_close']
    df['gap_open_percent'] = df['gap_open'] / df['previous_close'] * 100
    df = df.sort_values('gap_open_percent', ascending=False)
    return df