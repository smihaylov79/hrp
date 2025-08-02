from datetime import date, datetime
from urllib.parse import unquote
import time

import numpy as np
import pandas as pd
import yfinance as yf

from finance.models import DailyDataInvest, DailyData, SymbolsMapping, FundamentalsData


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
    df = df.rename(columns={0: 'symbol', 1: 'company_name', 2: 'open', 3: 'previous_close', 4: 'isin', 5: 'path'})
    df['gap_open'] = df['open'] - df['previous_close']
    df['gap_open_percent'] = df['gap_open'] / df['previous_close'] * 100
    df.replace([np.inf, -np.inf], 0, inplace=True)
    df.fillna(0, inplace=True)
    df = df.sort_values('gap_open_percent', ascending=False)
    return df


def convert_to_milliseconds(unix_ts):
    return unix_ts * 1000


def backup_chart(symbol, timeframe):
    interval_map = {
        "TIMEFRAME_D1": "1d",
        "TIMEFRAME_H1": "1h",
        "TIMEFRAME_M1": "1m"
    }
    interval = interval_map.get(timeframe, "1d")
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y", interval=interval)
        history = []
        for idx, row in hist.iterrows():
            history.append({
                "time": int(idx.timestamp()),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"])
            })
        data = ticker.info
        return history, data
    except Exception as e:
        return []


def get_official_symbol(invest_symbol, trade_symbol):
    if invest_symbol:
        symbol = invest_symbol.split('.')[0]
        if symbol:
            return symbol
    if trade_symbol:
        return trade_symbol.replace('#', '').split('.')[0]
    return None


def generate_symbol_mapping():
    invest_map = {
        item['isin_number']: (item['symbol'], item['company_name'])
        for item in DailyDataInvest.objects.filter(details__icontains='Stock').values('isin_number', 'symbol',
                                                                                      'company_name').distinct()
    }
    trade_map = {
        item['isin_number']: (item['symbol'], item['company_name'])
        for item in
        DailyData.objects.filter(details__icontains='Stock').values('isin_number', 'symbol', 'company_name').distinct()
    }

    all_isins = set(invest_map.keys()) | set(trade_map.keys())

    for isin in all_isins:
        trade_symbol, trade_name = trade_map.get(isin, (None, None))
        invest_symbol, invest_name = invest_map.get(isin, (None, None))

        official_symbol = get_official_symbol(invest_symbol, trade_symbol)
        name_metatrader = invest_name or trade_name

        SymbolsMapping.objects.update_or_create(
            isin_number=isin,
            defaults={
                'trade_symbol': trade_symbol,
                'invest_symbol': invest_symbol,
                'official_symbol': official_symbol,
                'name_metatrader': name_metatrader,
            }
        )


def parse_date(value):
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except Exception:
            return None
    elif isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return None
    return None


def fetch_fundamentals_data():
    symbols_mapping = SymbolsMapping.objects.filter(id__in=[237,248,251,335,489,635,695,825,1300,1460,1594,1633,1644,1806,1967,2262,2449,2683,3052,3077,3353,3503,3688,]
)
    today = date.today()
    errors = []
    for mapping in symbols_mapping:
        symbol = mapping.official_symbol
        if not symbol:
            continue
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            # if not mapping.industry or not mapping.sector or not mapping.country or not mapping.long_business_summary or not mapping.official_name:
            mapping.industry = info.get("industry") or mapping.industry
            mapping.sector = info.get("sector") or mapping.sector
            mapping.country = info.get("country") or mapping.country
            mapping.long_business_summary = info.get("longBusinessSummary") or mapping.long_business_summary
            mapping.official_name = info.get("longName") or info.get("shortName") or mapping.official_name
            mapping.save()
            officers = info.get("companyOfficers", [])
            ceo = next((o for o in officers if o.get('title', '').lower() == "chief executive officer"), {})
            # FundamentalsData.objects.create(
            #     extracted_date=today,
            #     symbol_mapping=mapping,
            #     symbol_yahoo=info.get("symbol"),
            #     name=info.get("shortName"),
            #     full_time_employees=info.get("fullTimeEmployees"),
            #     ex_dividend_date=parse_date(info.get("exDividendDate")),
            #     last_dividend_date=parse_date(info.get("lastDividendDate")),
            #     dividend_date=parse_date(info.get("dividendDate")),
            #     earnings_call_timestamp_start=parse_date(info.get("earningsCallStartDate")),
            #     beta=info.get("beta"),
            #     forward_pe=info.get("forwardPE"),
            #     market_cap=info.get("marketCap"),
            #     fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            #     fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
            #     price_to_sales_ttm=info.get("priceToSalesTrailing12Months"),
            #     fifty_day_average=info.get("fiftyDayAverage"),
            #     two_hundred_day_average=info.get("twoHundredDayAverage"),
            #     enterprise_value=info.get("enterpriseValue"),
            #     shares_outstanding=info.get("sharesOutstanding"),
            #     current_price=info.get("currentPrice"),
            #     price_to_book=info.get("priceToBook"),
            #     earnings_quarterly_growth=info.get("earningsQuarterlyGrowth"),
            #     trailing_eps=info.get("trailingEps"),
            #     forward_eps=info.get("forwardEps"),
            #     eps_ttm=info.get("epsTrailingTwelveMonths"),
            #     eps_forward=info.get("epsForward"),
            #     eps_current_year=info.get("epsCurrentYear"),
            #     price_eps_current_year=info.get("priceEpsCurrentYear"),
            #     earnings_growth=info.get("earningsGrowth"),
            #     revenue_growth=info.get("revenueGrowth"),
            #     last_dividend_value=info.get("lastDividendValue"),
            #     enterprise_to_revenue=info.get("enterpriseToRevenue"),
            #     enterprise_to_ebitda=info.get("enterpriseToEbitda"),
            #     fifty_two_week_low_change_percent=info.get("fiftyTwoWeekLowChangePercent"),
            #     fifty_two_week_high_change_percent=info.get("fiftyTwoWeekHighChangePercent"),
            #     fifty_two_week_change=info.get("52WeekChange"),
            #     target_high_price=info.get("targetHighPrice"),
            #     target_low_price=info.get("targetLowPrice"),
            #     target_median_price=info.get("targetMedianPrice"),
            #     recommendation_key=info.get("recommendationKey"),
            #     number_of_analyst_opinions=info.get("numberOfAnalystOpinions"),
            #     average_analyst_rating=info.get("averageAnalystRating"),
            #     trailing_peg_ratio=info.get("trailingPegRatio"),
            #     total_cash=info.get("totalCash"),
            #     total_cash_per_share=info.get("totalCashPerShare"),
            #     ebitda=info.get("ebitda"),
            #     total_debt=info.get("totalDebt"),
            #     total_revenue=info.get("totalRevenue"),
            #     revenue_per_share=info.get("revenuePerShare"),
            #     gross_profits=info.get("grossProfits"),
            #     operating_cashflow=info.get("operatingCashflow"),
            #     gross_margins=info.get("grossMargins"),
            #     ebitda_margins=info.get("ebitdaMargins"),
            #     operating_margins=info.get("operatingMargins"),
            #     ceo_name=ceo.get("name"),
            #     ceo_age=ceo.get("age"),
            # )
            FundamentalsData.objects.update_or_create(
                symbol_mapping=mapping,
                defaults={
                    'extracted_date': today,
                    'symbol_yahoo': info.get("symbol"),
                    'name': info.get("shortName"),
                    'full_time_employees': info.get("fullTimeEmployees"),
                    'ex_dividend_date': parse_date(info.get("exDividendDate")),
                    'last_dividend_date': parse_date(info.get("lastDividendDate")),
                    'dividend_date': parse_date(info.get("dividendDate")),
                    'earnings_call_timestamp_start': parse_date(info.get("earningsCallStartDate")),
                    'beta': info.get("beta"),
                    'forward_pe': info.get("forwardPE"),
                    'market_cap': info.get("marketCap"),
                    'fifty_two_week_low': info.get("fiftyTwoWeekLow"),
                    'fifty_two_week_high': info.get("fiftyTwoWeekHigh"),
                    'price_to_sales_ttm': info.get("priceToSalesTrailing12Months"),
                    'fifty_day_averagev': info.get("fiftyDayAverage"),
                    'two_hundred_day_average': info.get("twoHundredDayAverage"),
                    'enterprise_value': info.get("enterpriseValue"),
                    'shares_outstanding': info.get("sharesOutstanding"),
                    'current_price': info.get("currentPrice"),
                    'price_to_book': info.get("priceToBook"),
                    'earnings_quarterly_growth': info.get("earningsQuarterlyGrowth"),
                    'trailing_eps': info.get("trailingEps"),
                    'forward_eps': info.get("forwardEps"),
                    'eps_ttm': info.get("epsTrailingTwelveMonths"),
                    'eps_forward': info.get("epsForward"),
                    'eps_current_year': info.get("epsCurrentYear"),
                    'price_eps_current_year': info.get("priceEpsCurrentYear"),
                    'earnings_growth': info.get("earningsGrowth"),
                    'revenue_growth': info.get("revenueGrowth"),
                    'last_dividend_value': info.get("lastDividendValue"),
                    'enterprise_to_revenue': info.get("enterpriseToRevenue"),
                    'enterprise_to_ebitda': info.get("enterpriseToEbitda"),
                    'fifty_two_week_low_change_percent': info.get("fiftyTwoWeekLowChangePercent"),
                    'fifty_two_week_high_change_percent': info.get("fiftyTwoWeekHighChangePercent"),
                    'fifty_two_week_change': info.get("52WeekChange"),
                    'target_high_price': info.get("targetHighPrice"),
                    'target_low_price': info.get("targetLowPrice"),
                    'target_median_price': info.get("targetMedianPrice"),
                    'recommendation_key': info.get("recommendationKey"),
                    'number_of_analyst_opinions': info.get("numberOfAnalystOpinions"),
                    'average_analyst_rating': info.get("averageAnalystRating"),
                    'trailing_peg_ratio': info.get("trailingPegRatio"),
                    'total_cash': info.get("totalCash"),
                    'total_cash_per_share': info.get("totalCashPerShare"),
                    'ebitda': info.get("ebitda"),
                    'total_debt': info.get("totalDebt"),
                    'total_revenue': info.get("totalRevenue"),
                    'revenue_per_share': info.get("revenuePerShare"),
                    'gross_profits': info.get("grossProfits"),
                    'operating_cashflow': info.get("operatingCashflow"),
                    'gross_margins': info.get("grossMargins"),
                    'ebitda_margins': info.get("ebitdaMargins"),
                    'operating_margins': info.get("operatingMargins"),
                    'ceo_name': ceo.get("name"),
                    'ceo_age': ceo.get("age"), }
            )
            time.sleep(1)
        except Exception as e:
            errors.append(f'{symbol}: {e}')
    return errors
