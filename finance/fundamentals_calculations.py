import pandas as pd
import os
import requests
from datetime import date, datetime
import httpx


# async def get_news(symbol):
#     API_KEY_NEWS = os.environ.get("API_KEY_NEWS")
#     URL_NEWS = os.environ.get("URL_NEWS")
#     params = {
#         "api_token": API_KEY_NEWS,
#         "language": "en",
#         "limit": 5,
#         "symbols": symbol
#     }
#
#     async with httpx.AsyncClient() as client:
#         response = await client.get(URL_NEWS, params=params)
#         response.raise_for_status()
#         news_data = response.json().get("data", [])
#
#     for article in news_data:
#         if article.get("published_at"):
#             article["published_at"] = datetime.strptime(
#                 article["published_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
#             ).strftime("%B %d, %Y %H:%M %p")
#
#         sentiment_scores = [entity.get("sentiment_score") for entity in article.get("entities", []) if
#                             "sentiment_score" in entity]
#         article["sentiment_score"] = round(sum(sentiment_scores) / len(sentiment_scores),
#                                            2) if sentiment_scores else "N/A"
#
#     return news_data



def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None

    df = pd.DataFrame(prices, columns=['timestamp', 'open', 'high', 'low', 'close'])
    df['delta'] = df['close'].diff()

    df['gain'] = df['delta'].apply(lambda x: x if x > 0 else 0)
    df['loss'] = df['delta'].apply(lambda x: -x if x < 0 else 0)

    avg_gain = df['gain'].rolling(window=period).mean()
    avg_loss = df['loss'].rolling(window=period).mean()

    rs = avg_gain / avg_loss
    df['rsi'] = 100 - (100 / (1 + rs))

    return df['rsi'].iloc[-1]


def calculate_fair_price_fast(fundamentals):
    if fundamentals.eps_forward and fundamentals.forward_pe:
        return fundamentals.eps_forward * fundamentals.forward_pe
    return None


def calculate_ebit(fundamentals):
    ebit = fundamentals.total_revenue * fundamentals.operating_margins
    amortization = fundamentals.ebitda - ebit
    return ebit, amortization


def debt_to_equity(fundamentals):
    equity = fundamentals.market_cap - fundamentals.total_debt + fundamentals.total_cash
    return fundamentals.total_debt/equity


def calculate_cogs(fundamentals):
    gm_percent = fundamentals.gross_margins
    revenue = fundamentals.total_revenue
    gm_value = revenue * gm_percent
    cogs = revenue - gm_value

    return cogs, gm_value

