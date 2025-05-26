from django.shortcuts import render
from .models import *
# Create your views here.

def finance_home(request):
    return render(request, 'finance/finance_home.html')


