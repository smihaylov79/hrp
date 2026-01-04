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
from django.conf.urls.i18n import i18n_patterns

# from wagtail.admin import urls as wagtailadmin_urls
# from wagtail.documents import urls as wagtaildocs_urls
# from wagtail.images import urls as wagtailimages_urls
# from wagtail import urls as wagtail_urls

urlpatterns = [
    path('admin/', admin.site.urls),

    # path('wagtail-admin/', include(wagtailadmin_urls)),
    # path('documents/', include(wagtaildocs_urls)),
    # path('images/', include(wagtailimages_urls)),

    path('', HomeView.as_view(), name='home'),

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
    path('reading/', include('reading.urls')),
    path('income/', include('income.urls')),
    path('budget/', include('budget.urls')),
    path('i18n/', include('django.conf.urls.i18n')),

    # path('', include(wagtail_urls)),

]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
