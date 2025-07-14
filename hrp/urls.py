"""
URL configuration for hrp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from .views import *
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', HomeView.as_view(), name='home'),
    # path('', home, name='home'),
    path('users/', include('users.urls')),
    path('shopping/', include('shopping.urls')),
    path('inventory/', include('inventory.urls')),
    path('cooking/', include('cooking.urls')),
    path('entertainment/', include('entertainment.urls')),
    path('finance/', include('finance.urls')),
    path('forum/', include('forum.urls')),
    path('weather/', include('weather.urls')),
    path('reports/', include('reports.urls')),
    path('tasks/', include('taskmanager.urls')),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
