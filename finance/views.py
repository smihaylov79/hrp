from datetime import datetime, date
import pytz
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render, redirect

import os
import requests
from django.http import JsonResponse
from django.utils import timezone
import urllib.parse

from .models import DailyData, Market, DailyDataInvest, FundamentalsData, SymbolsMapping, InstrumentTypesTrade, InstrumentTypesInvest, MarginGroups

from .helpers import deep_clean, create_dataframe, convert_to_milliseconds, fetch_fundamentals_data, \
    generate_symbol_mapping, backup_chart, get_news, get_predicted_price, get_lstm_prediction
from .fundamentals_calculations import calculate_fair_price_fast, calculate_ebit, debt_to_equity, calculate_cogs, \
    calculate_rsi

# Create your views here.

API_KEY = os.environ.get("API_KEY")
API_KEY_NEWS = os.environ.get("API_KEY_NEWS")
URL_NEWS = os.environ.get("URL_NEWS")
NGROK_URL = os.environ.get("NGROK_URL")


def clean_percentage(value):
    """ Convert percentage strings like '5.723%' to rounded floats '5.72' """
    return f"{float(value.replace('%', '')):.2f}"


def format_market_cap(value):
    """ Convert market capitalization to billions """
    return f"{float(value) / 1_000_000_000:.2f}B"


def finance_home(request):
    markets = Market.objects.all()
    local_tz = timezone.get_current_timezone()

    for market in markets:
        market.current_status = "open" if market.is_open_now() else "closed"

        # Get today's open/close in market timezone
        market_tz = pytz.timezone(market.time_zone)
        now_market = timezone.now().astimezone(market_tz)
        today = now_market.date()

        open_dt = market_tz.localize(datetime.combine(today, market.open_time))
        close_dt = market_tz.localize(datetime.combine(today, market.close_time))

        market.utc_open = open_dt.astimezone(pytz.UTC).isoformat()
        market.utc_close = close_dt.astimezone(pytz.UTC).isoformat()

        # Countdown label
        delta = market.time_until_event()
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        label = "Closes in" if market.current_status == "open" else "Opens in"
        market.countdown_text = f"{label} {hours}h {minutes}m"

    context = {'markets': markets}

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
                instrument_type=row['instrument_type'],
                exchange=row['exchange'],
                base_currency=row['base_currency'],
                margin_group=row['margin_group'],
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
    last_extraction = DailyDataInvest.objects.order_by('-date').first()
    extracted_data = None
    top_gainers = None
    top_loosers = None
    number_of_symbols = 0

    if last_extraction:
        extracted_data = DailyDataInvest.objects.filter(date=last_extraction.date)
        top_gainers = extracted_data.order_by('-gap_open_percentage')[:10]
        top_loosers = extracted_data.order_by('gap_open_percentage')[:10]
        number_of_symbols = extracted_data.count()
    if request.method == 'POST':
        url = f"{NGROK_URL}symbols-invest"
        response = requests.get(url, timeout=15)
        data = response.json()

        df = create_dataframe(data)
        today = date.today()
        records = []
        for _, row in df.iterrows():
            records.append(DailyDataInvest(
                date=today,
                symbol=row['symbol'],
                company_name=row['company_name'],
                open_price=row['open'],
                previous_close_price=row['previous_close'],
                gap_open_price=row['gap_open'],
                gap_open_percentage=row['gap_open_percent'],
                isin_number=row['isin'],
                details=row['path'],
                instrument_type=row['instrument_type'],
                exchange=row['exchange'],
                base_currency=row['base_currency'],
                part_from_index=row['part_from_index'],
            ))
        extracted_data = DailyDataInvest.objects.bulk_create(records)
        number_of_symbols = len(records)

    context = {
        'last_extraction': last_extraction,
        'data': extracted_data if extracted_data else {},
        'number_of_symbols': number_of_symbols,
        'gainers': top_gainers if top_gainers else [],
        'loosers': top_loosers if top_loosers else [],
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


@login_required
def screener_settings(request):
    errors = []
    if request.method == 'POST':
        if request.user.is_authenticated and request.user.is_superuser:
            action = request.POST.get('action')
            if action == 'generate_symbols':
                generate_symbol_mapping()
            elif action == 'fetch_fundamentals':
                errors = fetch_fundamentals_data()
    is_superuser = request.user.is_authenticated and request.user.is_superuser
    context = {
        'is_superuser': is_superuser,
        'errors': errors
    }
    return render(request, "finance/screener_settings.html", context)


def screener_view(request):
    is_superuser = request.user.is_authenticated and request.user.is_superuser

    data = FundamentalsData.objects.filter(symbol_yahoo__isnull=False)
    sectors = SymbolsMapping.objects.values_list('sector', flat=True).distinct()
    industries = SymbolsMapping.objects.values_list('industry', flat=True).distinct()
    countries = SymbolsMapping.objects.values_list('country', flat=True).distinct()


    context = {
        'is_superuser': is_superuser,
        'data': data,
        'sectors': sectors,
        'industries': industries,
        'countries': countries
    }
    return render(request, "finance/screener.html", context)


def delete_last_data(request):
    if request.method == "POST":
        latest_data = DailyData.objects.order_by('-date').values_list('date', flat=True).first()
        if latest_data:
            DailyData.objects.filter(date=latest_data).delete()
    return redirect('trade')


def delete_last_data_invest(request):
    if request.method == "POST":
        latest_data = DailyDataInvest.objects.order_by('-date').values_list('date', flat=True).first()
        if latest_data:
            DailyDataInvest.objects.filter(date=latest_data).delete()
    return redirect('invest')


def trade_details(request):
    last_date = DailyData.objects.order_by('-date').values_list('date', flat=True).first()
    data = DailyData.objects.filter(date=last_date).order_by('-gap_open_percentage')
    markets = Market.objects.all()
    types = InstrumentTypesTrade.objects.all()
    margin = MarginGroups.objects.all()
    context = {
        'data': data,
        'markets': markets,
        'types': types,
        'margin': margin
    }

    return render(request, 'finance/trade_details.html', context)


def invest_details(request):
    last_date = DailyDataInvest.objects.order_by('-date').values_list('date', flat=True).first()
    data = DailyDataInvest.objects.filter(date=last_date).order_by('-gap_open_percentage')
    indices = DailyDataInvest.objects.filter(part_from_index__isnull=False).values_list('part_from_index', flat=True).distinct()
    markets = Market.objects.all()

    types = InstrumentTypesInvest.objects.all()
    for s in data:
        f_data = FundamentalsData.objects.filter(symbol_mapping__invest_symbol=s.symbol).first()
        if f_data:
            s.ev_ebitda = f_data.enterprise_to_ebitda

    context = {
        'data': data,
        'markets': markets,
        'types': types,
        'indices': indices
    }

    return render(request, 'finance/invest_details.html', context)


def symbol_details(request):
    symbol = request.GET.get("symbol")
    timeframe = request.GET.get("timeframe", "TIMEFRAME_D1")
    data, history = {}, []
    ohlc_data = []
    symbol = symbol.replace('%23', '#')
    official_symbol = SymbolsMapping.objects.filter(Q(trade_symbol=symbol) | Q(invest_symbol=symbol) | Q(official_symbol=symbol)).first()
    if symbol:
        encoded_symbol = requests.utils.quote(symbol, safe='')
        symbol_url = f"{NGROK_URL}symbol-info/{encoded_symbol}"
        history_url = f"{NGROK_URL}price-history/{encoded_symbol}?timeframe={timeframe}&count=365"
        try:
            response = requests.get(symbol_url, timeout=5)
            response.raise_for_status()
            data = response.json()

            hist_response = requests.get(history_url, timeout=5)
            hist_response.raise_for_status()
            history = hist_response.json()
            ohlc_data = [
                [convert_to_milliseconds(item['time']),
                 item['open'],
                 item['high'],
                 item['low'],
                 item['close']
                 ]
                for item in history
            ]
        except requests.RequestException:
            if symbol.startswith("#"):
                alt_symbol = symbol[1:]
            else:
                alt_symbol = "#" + symbol

            encoded_symbol = requests.utils.quote(alt_symbol, safe='')

            alt_symbol_url = f"{NGROK_URL}symbol-info/{encoded_symbol}"
            alt_history_url = f"{NGROK_URL}price-history/{encoded_symbol}?timeframe={timeframe}&count=365"

            try:
                response = requests.get(alt_symbol_url, timeout=5)
                response.raise_for_status()
                data = response.json()

                hist_response = requests.get(alt_history_url, timeout=5)
                hist_response.raise_for_status()
                history = hist_response.json()

                ohlc_data = [
                    [convert_to_milliseconds(item['time']),
                     item['open'],
                     item['high'],
                     item['low'],
                     item['close']]
                    for item in history
                ]
            except requests.RequestException:
                try:
                    yahoo_symbol = official_symbol.official_symbol if official_symbol else symbol.replace('#', '')
                    history = backup_chart(yahoo_symbol, timeframe)[0]
                    ohlc_data = [
                        [item['time'] * 1000, item['open'], item['high'], item['low'], item['close']]
                        for item in history
                    ]
                    data = backup_chart(yahoo_symbol, timeframe)[1]
                except Exception:
                    data = {"error": f"Данните не са налични! Опитай отново като добавиш или премахнеш '#' пред символа. Възможно е сървърът да е в режим invest"}

    fundamentals_data = None
    news_data = None
    fair_price = None
    debt_equity = None
    ebit = None
    amortization = None
    cogs = None
    gm_value = None
    rsi = None

    if official_symbol:
        symbol_from_official = official_symbol.official_symbol
        fundamentals_data = FundamentalsData.objects.filter(symbol_yahoo=symbol_from_official).first()
        news_data = get_news(symbol_from_official)
        fair_price = calculate_fair_price_fast(fundamentals_data) if fundamentals_data else None
        ebit = calculate_ebit(fundamentals_data)[0] if fundamentals_data else None
        amortization = calculate_ebit(fundamentals_data)[1] if fundamentals_data else None
        debt_equity = debt_to_equity(fundamentals_data) if fundamentals_data else None
        cogs = calculate_cogs(fundamentals_data)[0] if fundamentals_data else None
        gm_value = calculate_cogs(fundamentals_data)[1] if fundamentals_data else None
        rsi = calculate_rsi(ohlc_data)

    context = {
        'data': data,
        'symbol': symbol,
        'history': history,
        'ohlc_data': ohlc_data,
        'selected_timeframe': timeframe,
        'fundamentals': fundamentals_data,
        'news': news_data,
        'fair_price': fair_price,
        'ebit': ebit,
        'debt_equity': debt_equity,
        'amortization': amortization,
        'cogs': cogs,
        'gm_value': gm_value,
        'rsi': rsi,
    }
    return render(request, 'finance/symbol_details.html', context)


def check_margin(request, symbol):
    if request.method == 'POST':
        symbol = request.POST.get('symbol')
        lot = request.POST.get('lot')
        action = request.POST.get('action', 'ORDER_TYPE_BUY')
        url = f"{NGROK_URL}calculate-margin"
        params = {'lot': lot, 'symbol': symbol, 'action': action}
        try:
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            margin = data.get('margin')
            currency = data.get('currency')
        except Exception as e:
            margin = None
            currency = None
        context = {
            'margin': margin, 'symbol': symbol, 'currency': currency, 'lot': lot, 'action': action
        }
        return render(request, 'finance/margin_form.html', context)
    return render(request, 'finance/margin_form.html', {'symbol': symbol})


def predict_price_view(request):
    symbol = request.GET.get("symbol", "EURUSD")
    timeframe = request.GET.get("timeframe", "D1")
    count = int(request.GET.get("count", 30))
    window = int(request.GET.get("window", 5))

    prediction = get_predicted_price(symbol, timeframe, count, window)
    return JsonResponse(prediction)


# def prediction_page(request):
#     symbol = request.GET.get("symbol", "")
#     timeframe = request.GET.get("timeframe", "D1")
#     count = int(request.GET.get("count", 30))
#     window = int(request.GET.get("window", 5))
#
#     prediction = None
#     historical_data = []
#
#     if symbol:
#         prediction = get_predicted_price(symbol, timeframe, count, window)
#         # Fetch historical prices from FastAPI
#         history_url = f"{NGROK_URL}price-history/{symbol}?timeframe={timeframe}&count={count}"
#         try:
#             response = requests.get(history_url)
#             historical_data = response.json()
#         except Exception as e:
#             historical_data = []
#
#     context = {
#         "symbol": symbol,
#         "timeframe": timeframe,
#         "prediction": prediction,
#         "historical_data": historical_data,
#     }
#     return render(request, "finance/prediction_page.html", context)

def prediction_page(request):
    symbol = request.GET.get("symbol", "")
    timeframe = request.GET.get("timeframe", "D1")
    count = int(request.GET.get("count", 30))
    window = int(request.GET.get("window", 5))
    forecast_days = int(request.GET.get("forecast_days", 5))
    timeframes = ["D1", "M1", "M5", "M15", "M30", "H1", "H4", "W1", "MN1"]
    forecast_points = []
    encoded_symbol = urllib.parse.quote(symbol)

    sma_prediction = None
    lstm_prediction = None
    lstm_next_day = None

    prediction = None
    historical_data = []

    if symbol:
        sma_prediction = get_predicted_price(symbol, timeframe, count, window)
        lstm_prediction = get_lstm_prediction(symbol, timeframe, count)
        lstm_next_day = lstm_prediction['predicted_prices'][0]
        prediction = get_predicted_price(symbol, timeframe, count, window)
        history_url = f"{NGROK_URL}price-history/{encoded_symbol}?timeframe={timeframe}&count={count}"
        try:
            response = requests.get(history_url)
            historical_data = response.json()
            if isinstance(historical_data, str):
                historical_data = []
        except Exception as e:
            historical_data = []

        # Simulate multi-day forecast using SMA recursively
        closes = [row["close"] for row in historical_data]

        for i in range(forecast_days):
            if len(closes) >= window:
                next_price = sum(closes[-window:]) / window
                closes.append(next_price)
                forecast_points.append(next_price)



    context = {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": count,
        "window": window,
        "forecast_days": forecast_days,
        "prediction": prediction,
        "forecast_points": forecast_points,
        "historical_data": historical_data,
        'timeframes': timeframes,
        'sma_prediction': sma_prediction,
        'lstm_prediction': lstm_prediction,
        'lstm_next_day': lstm_next_day,
    }
    return render(request, "finance/prediction_page.html", context)
