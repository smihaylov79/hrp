from datetime import datetime
import pytz
from django.shortcuts import render

import os
import requests
# Create your views here.

API_KEY = os.environ.get("API_KEY")
API_KEY_NEWS = os.environ.get("API_KEY_NEWS")
URL_NEWS = os.environ.get("URL_NEWS")

# target_exchanges = ["NASDAQ", "NYSE", "London", "XETRA", "Tokyo", "Hong Kong"]



# def parse_market_time(market):
#     exchange = next((e for e in timezone_map if e in market.get("primary_exchanges", "")), None)
#     if not exchange:
#         return market
#     tz = pytz.timezone(timezone_map[exchange])
#
#     today = datetime.now(tz).date()
#     open_str = market.get("local_open", "00:00")
#     close_str = market.get("local_close", "00:00")
#
#     # Construct timezone-aware datetime objects
#     market["utc_open"] = tz.localize(datetime.strptime(f"{today} {open_str}", "%Y-%m-%d %H:%M")).astimezone(pytz.utc)
#     market["utc_close"] = tz.localize(datetime.strptime(f"{today} {close_str}", "%Y-%m-%d %H:%M")).astimezone(pytz.utc)
#     return market

def clean_percentage(value):
    """ Convert percentage strings like '5.723%' to rounded floats '5.72' """
    return f"{float(value.replace('%', '')):.2f}"


def format_market_cap(value):
    """ Convert market capitalization to billions """
    return f"{float(value) / 1_000_000_000:.2f}B"


def finance_home(request):
    market_url = f"https://www.alphavantage.co/query?function=MARKET_STATUS&apikey={API_KEY}"
    response = requests.get(market_url)
    market_data = response.json().get("markets", [])
    url_top_movers = f"https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey={API_KEY}"
    response = requests.get(url_top_movers)
    top_movers = response.json()

    for stock in top_movers.get("top_gainers", [])[:10]:
        stock["change_percentage"] = clean_percentage(stock["change_percentage"])

    for stock in top_movers.get("top_losers", [])[:10]:
        stock["change_percentage"] = clean_percentage(stock["change_percentage"])

    timezone_map = {
        "NASDAQ": "America/New_York",
        "NYSE": "America/New_York",
        "London": "Europe/London",
        "XETRA": "Europe/Berlin",
        "Tokyo": "Asia/Tokyo",
        "Hong Kong": "Asia/Hong_Kong"
    }

    # Filter & process only relevant markets
    def enrich_market(market):
        exchange = next((e for e in timezone_map if e in market.get("primary_exchanges", "")), None)
        if not exchange:
            return None
        tz = pytz.timezone(timezone_map[exchange])
        today = datetime.now(tz).date()

        # Build open/close datetimes and convert to UTC
        open_time = tz.localize(datetime.strptime(f"{today} {market.get('local_open')}", "%Y-%m-%d %H:%M"))
        close_time = tz.localize(datetime.strptime(f"{today} {market.get('local_close')}", "%Y-%m-%d %H:%M"))

        market["exchange"] = exchange
        market["utc_open"] = open_time.astimezone(pytz.utc).isoformat()
        market["utc_close"] = close_time.astimezone(pytz.utc).isoformat()
        return market

    filtered_markets = [enrich_market(m) for m in market_data if enrich_market(m)]
    context = {
        "market_data": filtered_markets,
        "top_gainers": top_movers.get("top_gainers", [])[:10],
        "top_losers": top_movers.get("top_losers", [])[:10]
    }

    return render(request, "finance/finance_home.html", context)


def ticker_details(request, ticker):
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={API_KEY}'
    r = requests.get(url)
    data = r.json()

    data["MarketCapitalization"] = format_market_cap(data["MarketCapitalization"])
    data["EBITDA"] = format_market_cap(data["EBITDA"])


    stock_info = {
         'symbol': data.get( 'Symbol', "N/A"),
         'name': data.get( 'Name', "N/A"),
         'ebitda': data.get( 'EBITDA', "N/A"),
         'country': data.get( 'Country', "N/A"),
         'sector': data.get( 'Sector', "N/A"),
         'industry': data.get( 'Industry', "N/A"),
         'trailingpe': data.get( 'TrailingPE', "N/A"),
         'forwardpe': data.get( 'ForwardPE', "N/A"),
         'analysttargetprice': data.get( 'AnalystTargetPrice', "N/A"),
         'pegratio': data.get( 'PEGRatio', "N/A"),
         'peratio': data.get( 'PERatio', "N/A"),
         'evtorevenue': data.get( 'EVToRevenue', "N/A"),
         'evtoebitda': data.get( 'EVToEBITDA', "N/A"),
         'beta': data.get( 'Beta', "N/A"),
         'eps': data.get( 'EPS', "N/A"),
         'revenuepersharettm': data.get( 'RevenuePerShareTTM', "N/A"),
         '52weekhigh': data.get( '52WeekHigh', "N/A"),
         '52weeklow': data.get( '52WeekLow', "N/A"),
         '50daymovingaverage': data.get( '50DayMovingAverage', "N/A"),
         '200daymovingaverage': data.get( '200DayMovingAverage', "N/A"),
         'exdividenddate': data.get( 'ExDividendDate', "N/A"),
         'marketcapitalization': data.get( 'MarketCapitalization', "N/A"),
         'description': data.get('Description', "N/A")

    }
    context = {'stock_info': stock_info}
    return render(request, 'finance/ticker_details.html', context)

def finance_news(request):
    ticker = request.GET.get('ticker', "").upper()
    params = {
        "api_token": API_KEY_NEWS,
        "language": "en",
        "limit": 5
    }

    if ticker:
        params['symbols'] = ticker

    response = requests.get(URL_NEWS, params=params)
    news_data = response.json().get("data", [])

    for article in news_data:
        if article.get("published_at"):
            article["published_at"] = datetime.strptime(article["published_at"], "%Y-%m-%dT%H:%M:%S.%fZ").strftime(
                "%B %d, %Y %H:%M %p")
        sentiment_scores = [entity["sentiment_score"] for entity in article.get("entities", []) if
                            "sentiment_score" in entity]
        article["sentiment_score"] = round(sum(sentiment_scores) / len(sentiment_scores),
                                           2) if sentiment_scores else "N/A"

    context = {'ticker': ticker, 'news': news_data}
    return render(request, "finance/news.html", context)


def portfolio(request):
    return render(request, 'finance/portfolio.html')


def markets(request):

    return render(request, 'finance/markets.html')


def screener(request):
    return render(request, 'finance/screener.html')


