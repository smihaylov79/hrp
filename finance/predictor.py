import pandas as pd
from .models import DailyData, DailyDataInvest
from sklearn.ensemble import RandomForestRegressor

import numpy as np

def run_prediction_model(date):
    drop_cols = ['gap_open_percentage', 'date', 'symbol', 'company_name', 'isin_number',
                 'details', 'part_from_index', 'margin_group']
    categorical_cols = ['exchange', 'instrument_type', 'base_currency']
    # Combine historical data from both models
    data_qs = list(DailyData.objects.exclude(date=date).values()) + \
              list(DailyDataInvest.objects.exclude(date=date).values())
    df = pd.DataFrame(data_qs)

    if df.empty:
        return "No historical data available."

    # Feature engineering
    df['momentum'] = (df['open_price'] - df['previous_close_price']) / df['previous_close_price']
    df.fillna('', inplace=True)  # Handle nulls
    df.replace('', np.nan, inplace=True)
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.fillna(0, inplace=True)

    df = pd.get_dummies(df, columns=[col for col in categorical_cols if col in df.columns])

    # Train model
    X = df.drop(columns=[col for col in drop_cols if col in df.columns])
    y = df['gap_open_percentage']

    model = RandomForestRegressor()
    model.fit(X, y)

    # Predict on selected date
    today_qs = list(DailyData.objects.filter(date=date).values()) + \
               list(DailyDataInvest.objects.filter(date=date).values())
    today_df = pd.DataFrame(today_qs)


    today_df.replace('', np.nan, inplace=True)

    today_df.replace([np.inf, -np.inf], np.nan, inplace=True)
    today_df.fillna(0, inplace=True)

    if today_df.empty:
        return "No data for selected date."

    today_df['momentum'] = (today_df['open_price'] - today_df['previous_close_price']) / today_df['previous_close_price']
    today_df.fillna('', inplace=True)
    today_df = pd.get_dummies(today_df, columns=['exchange', 'instrument_type', 'base_currency'])
    today_df = today_df.reindex(columns=X.columns, fill_value=0)

    preds = model.predict(today_df)
    today_df['predicted_gap'] = preds

    top_gainer = today_df.sort_values(by='predicted_gap', ascending=False).iloc[0]
    top_loser = today_df.sort_values(by='predicted_gap').iloc[0]

    return {
        'gainer': top_gainer['symbol'],
        'loser': top_loser['symbol'],
        'gainer_gap': top_gainer['predicted_gap'],
        'loser_gap': top_loser['predicted_gap']
    }
