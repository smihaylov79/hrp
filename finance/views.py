from datetime import datetime, date
import pytz
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

import os
import requests
from django.http import JsonResponse
from .models import DailyData

from finance.helpers import deep_clean, create_dataframe

# Create your views here.

API_KEY = os.environ.get("API_KEY")
API_KEY_NEWS = os.environ.get("API_KEY_NEWS")
URL_NEWS = os.environ.get("URL_NEWS")
NGROK_URL = os.environ.get("NGROK_URL")


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
    # url_top_movers = f"https://www.alphavantage.co/query?function=TOP_GAINERS_LOSERS&apikey={API_KEY}"
    # response = requests.get(url_top_movers)
    # top_movers = response.json()

    # print(market_data)
    #
    # for stock in top_movers.get("top_gainers", [])[:10]:
    #     stock["change_percentage"] = clean_percentage(stock["change_percentage"])
    #
    # for stock in top_movers.get("top_losers", [])[:10]:
    #     stock["change_percentage"] = clean_percentage(stock["change_percentage"])

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
        # "top_gainers": top_movers.get("top_gainers", [])[:10],
        # "top_losers": top_movers.get("top_losers", [])[:10]
    }

    return render(request, "finance/finance_home.html", context)


def trade(request):
    last_extraction = DailyData.objects.order_by('-date').first()
    extracted_data = None
    top_gainers = None
    top_loosers = None
    number_of_symbols = 0

    if last_extraction:
        extracted_data = DailyData.objects.filter(date=last_extraction.date)
        top_gainers = extracted_data.order_by('-gap_open_percentage')[:10]
        top_loosers = extracted_data.order_by('gap_open_percentage')[:10]
        number_of_symbols = extracted_data.count()
    if request.method == 'POST':
        url = f"{NGROK_URL}symbols"
        response = requests.get(url, timeout=15)
        data = response.json()
        df = create_dataframe(data)
        today = date.today()
        records = []
        for _, row in df.iterrows():
            records.append(DailyData(
                date=today,
                symbol=row['symbol'],
                company_name=row['company_name'],
                open_price=row['open'],
                previous_close_price=row['previous_close'],
                gap_open_price=row['gap_open'],
                gap_open_percentage=row['gap_open_percent'],
                isin_number=row['isin'],
                details=row['path'],
            ))
        extracted_data = DailyData.objects.bulk_create(records)
        number_of_symbols = len(records)

    context = {
        'last_extraction': last_extraction,
        'data': extracted_data if extracted_data else {},
        'number_of_symbols': number_of_symbols,
        'gainers': top_gainers if top_gainers else [],
        'loosers': top_loosers if top_loosers else [],
    }


    return render(request, "finance/trade.html", context)


def invest(request):
    context = {

    }
    return render(request, "finance/invest.html", context)


def ticker_details(request, ticker):
    url = f'https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={API_KEY}'
    r = requests.get(url)
    data = r.json()

    try:
        data["MarketCapitalization"] = format_market_cap(data["MarketCapitalization"])
    except:
        data["MarketCapitalization"] = 'N/A'

    try:
        data["EBITDA"] = format_market_cap(data["EBITDA"])
    except:
        data["EBITDA"] = 'N/A'

    stock_info = {
        'symbol': data.get('Symbol', "N/A"),
        'name': data.get('Name', "N/A"),
        'ebitda': data.get('EBITDA', "N/A"),
        'country': data.get('Country', "N/A"),
        'sector': data.get('Sector', "N/A"),
        'industry': data.get('Industry', "N/A"),
        'trailingpe': data.get('TrailingPE', "N/A"),
        'forwardpe': data.get('ForwardPE', "N/A"),
        'analysttargetprice': data.get('AnalystTargetPrice', "N/A"),
        'pegratio': data.get('PEGRatio', "N/A"),
        'peratio': data.get('PERatio', "N/A"),
        'evtorevenue': data.get('EVToRevenue', "N/A"),
        'evtoebitda': data.get('EVToEBITDA', "N/A"),
        'beta': data.get('Beta', "N/A"),
        'eps': data.get('EPS', "N/A"),
        'revenuepersharettm': data.get('RevenuePerShareTTM', "N/A"),
        '52weekhigh': data.get('52WeekHigh', "N/A"),
        '52weeklow': data.get('52WeekLow', "N/A"),
        '50daymovingaverage': data.get('50DayMovingAverage', "N/A"),
        '200daymovingaverage': data.get('200DayMovingAverage', "N/A"),
        'exdividenddate': data.get('ExDividendDate', "N/A"),
        'marketcapitalization': data.get('MarketCapitalization', "N/A"),
        'description': data.get('Description', "N/A")

    }
    # News retrieval
    params = {
        "api_token": API_KEY_NEWS,
        "language": "en",
        "limit": 5,
        "symbols": ticker.upper()
    }

    response = requests.get(URL_NEWS, params=params)
    news_data = response.json().get("data", [])

    for article in news_data:
        if article.get("published_at"):
            article["published_at"] = datetime.strptime(
                article["published_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ).strftime("%B %d, %Y %H:%M %p")

        sentiment_scores = [entity.get("sentiment_score") for entity in article.get("entities", []) if
                            "sentiment_score" in entity]
        article["sentiment_score"] = round(sum(sentiment_scores) / len(sentiment_scores),
                                           2) if sentiment_scores else "N/A"

    context = {
        'stock_info': stock_info,
        'news': news_data}
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

@login_required
def portfolio(request):
    return render(request, 'finance/portfolio.html')


def markets(request):
    return render(request, 'finance/markets.html')


def screener(request):
    symbol = request.GET.get("symbol")
    data = {}
    if symbol:
        url = f"{NGROK_URL}tick/{symbol}"
        symbol = symbol.replace('%23', '#')
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            data = {"error": str(e)}

    context = {
        "symbol": symbol,
        "data": data
    }
    return render(request, "finance/screener.html", context)


def delete_last_data(request):
    if request.method == "POST":
        latest_data = DailyData.objects.order_by('-date').values_list('date', flat=True).first()
        if latest_data:
            DailyData.objects.filter(date=latest_data).delete()
    return redirect('mt_active')


def trade_details(request):
    last_date = DailyData.objects.order_by('-date').values_list('date', flat=True).first()
    data = DailyData.objects.filter(date=last_date).order_by('-gap_open_percentage')
    context = {
        'data': data,
    }

    return render(request, 'finance/trade_details.html', context)


# def symbol_details(request):
#     symbol = request.GET.get("symbol")
#     data = {}
#     if symbol:
#         url = f"{NGROK_URL}tick/{symbol}"
#         symbol = symbol.replace('%23', '#')
#         try:
#             response = requests.get(url, timeout=5)
#             response.raise_for_status()
#             data = response.json()
#         except requests.RequestException as e:
#             data = {"error": str(e)}
#
#     context = {
#         'data': data,
#         'symbol': symbol
#     }
#     return render(request, 'finance/symbol_details.html', context)


def symbol_details(request):
    symbol = request.GET.get("symbol")
    data = {}
    if symbol:
        url = f"{NGROK_URL}symbol-info/{symbol}"
        symbol = symbol.replace('%23', '#')
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            data = {"error": str(e)}

    context = {
        'data': data,
        'symbol': symbol
    }
    return render(request, 'finance/symbol_details.html', context)