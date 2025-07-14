from django.shortcuts import render
import pandas as pd


def entertainment_home(request):
    return render(request, 'entertainment/entertainment_home.html')


def travel(request):
    return render(request, 'entertainment/travel.html')


def reading(request):
    return render(request, 'entertainment/reading.html')


def movies(request):
    return render(request, 'entertainment/movies.html')


def games(request):
    return render(request, 'entertainment/games.html')


import pandas as pd


def calculate_optimal_upgrades(current_levels, current_loyalty, target_loyalty, available_resources):
    resources = {
        'Level': list(range(1, 21)),
        'AC1': [0, 700, 2500, 4400, 8000, 14400, 25900, 46500, 83800, 150800, 271400, 325700, 390800, 469000, 562800,
                675400, 810500, 972600, 1200000, 1400000],
        'AC2': [0, 2200, 7400, 13300, 23900, 43100, 77600, 139600, 251300, 452300, 814100, 977100, 1200000, 1400000,
                1700000, 2000000, 2400000, 2900000, 3500000, 4200000],
        'AC3': [0, 4400, 14800, 26600, 47900, 86200, 155100, 279200, 502600, 904700, 1600000, 2000000, 2300000, 2800000,
                3400000, 4100000, 4900000, 5800000, 7000000, 8400000],
        'AC4': [0, 7400, 24600, 44300, 79800, 143600, 258500, 465400, 837700, 1500000, 2700000, 3300000, 3900000,
                4700000, 5600000, 6800000, 8100000, 9700000, 11700000, 14000000]
    }


    cob_df = pd.DataFrame(resources)

    for cob, current_level in current_levels.items():
        cob_df.loc[:current_level - 1, cob] = 0  # ✅ Set cost to zero for past upgrades

    loyalty_needed = target_loyalty - current_loyalty
    if loyalty_needed <= 0:
        return {"message": "You already have enough loyalty!"}

    cob_df_2 = cob_df.melt('Level', var_name='Coalition', value_name='Cost')
    cob_df_2 = cob_df_2[cob_df_2['Cost'] > 0]  # ✅ Remove past upgrades
    cob_df_2.sort_values(by="Cost", ascending=True, inplace=True)
    cob_df_2.reset_index(drop=True, inplace=True)

    upgrade_path = {}
    total_resources_spent = 0
    current_total_loyalty = current_loyalty

    while current_total_loyalty < target_loyalty:
        materials = cob_df_2['Cost'].iloc[0]
        total_resources_spent += materials
        cob_name = cob_df_2['Coalition'].iloc[0]
        cob_level = cob_df_2['Level'].iloc[0]
        upgrade_path[cob_name] = cob_level
        cob_df_2.drop(cob_df_2.index[[0]], inplace=True)
        current_total_loyalty += 100

    additional_resources_needed = total_resources_spent - available_resources

    return {
        "upgrade_path": dict(sorted(upgrade_path.items())),
        "total_resources_spent": total_resources_spent,
        "additional_resources_needed": max(0, additional_resources_needed),
        "final_loyalty": current_total_loyalty
    }


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
