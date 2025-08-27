from django.shortcuts import render
from .utils import calculate_optimal_upgrades


def entertainment_home(request):
    return render(request, 'entertainment/entertainment_home.html')


def travel(request):
    return render(request, 'entertainment/travel.html')


# def reading(request):
#     return render(request, 'entertainment/reading_home.html')


def movies(request):
    return render(request, 'entertainment/movies.html')


def games(request):
    return render(request, 'entertainment/games.html')


def game_calculator(request):
    if request.method == "POST":
        current_levels = {key: int(request.POST.get(key, 1)) for key in ["AC1", "AC2", "AC3", "AC4"]}
        current_loyalty = int(request.POST.get("current_loyalty", 0))
        target_loyalty = int(request.POST.get("target_loyalty", 0))
        available_resources = int(request.POST.get("available_resources", 0))

        upgrade_result = calculate_optimal_upgrades(current_levels, current_loyalty, target_loyalty,
                                                    available_resources)

        needed_materials = upgrade_result.get("additional_resources_needed", 0)
        available = {
            "Empty": int(request.POST.get("empty_available", 0)),
            "Food": int(request.POST.get("food_available", 0)),
            "Marble": int(request.POST.get("marble_available", 0)),
            "Ale": int(request.POST.get("ale_available", 0))
        }

        income_per_hour = {
            "Empty": int(request.POST.get("empty_income", 0)),
            "Food": int(request.POST.get("food_income", 0)),
            "Marble": int(request.POST.get("marble_income", 0)),
            "Ale": int(request.POST.get("ale_income", 0))
        }

        total_available = sum(available.values())
        total_income = sum(income_per_hour.values())

        missing_resources = needed_materials - total_available
        needed_gathering_time = round(missing_resources / total_income,
                                      2) if missing_resources > 0 and total_income > 0 else 0

        workshop_count = int(request.POST.get("workshop_count", 1))
        processing_rate = int(request.POST.get("processing_rate", 100))
        total_processing_capacity = workshop_count * processing_rate

        resources_to_process = needed_materials

        needed_processing_time = round(resources_to_process / total_processing_capacity,
                                       2) if resources_to_process > 0 and total_processing_capacity > 0 else 0

        ac_names = ["AC1", "AC2", "AC3", "AC4"]
        resources_list = ["Empty","Food","Marble","Ale"]

        context = {"upgrade_result": upgrade_result, "needed_gathering_time": needed_gathering_time,
                   "needed_processing_time": needed_processing_time, 'ac_names': ac_names, 'resources_list': resources_list}
        return render(request, "entertainment/calculator.html", context)

    return render(request, "entertainment/calculator.html", {})
