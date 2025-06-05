from django.shortcuts import render
import yfinance as yf
from .models import *
# Create your views here.


def finance_home(request):
    return render(request, 'finance/finance_home.html')


def finance_news(request):

    return render(request, "finance/news.html")


def portfolio(request):
    return render(request, 'finance/portfolio.html')


def markets(request):
    return render(request, 'finance/markets.html')


def screener(request):
    return render(request, 'finance/screener.html')


