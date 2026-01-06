from django.urls import path, include

urlpatterns = [
    path("change/", include("fastapps.change_calculator.urls")),
    # path("vat/", include("fastapps.vat_calculator.urls")),
    # path("units/", include("fastapps.unit_converter.urls")),
]
