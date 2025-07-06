from collections import defaultdict


def calculate_price_changes(shopping_data):
    product_prices = defaultdict(list)
    for entry in shopping_data:
        product_prices[entry['product__name']].append((entry['shopping__date'], entry['price']))

    price_changes = []
    for product, price in product_prices.items():
        if len(price) < 2:
            continue
        min_price = min(price, key=lambda x: x[1])
        max_price = max(price, key=lambda x: x[1])

        direction = 'увеличение' if max_price[0] > min_price[0] else 'намаление'
        difference = abs(max_price[1] - min_price[1])

        price_changes.append({'product': product,
                              'direction': direction,
                              'change': difference,
                              })
    increase = filter(lambda x: x['direction'] == 'увеличение', price_changes)
    decrease = filter(lambda x: x['direction'] == 'намаление', price_changes)
    top_increase = sorted(increase, key=lambda x: x['change'], reverse=True)
    top_decrease = sorted(decrease, key=lambda x: x['change'], reverse=True)
    # changes = sorted(price_changes, key=lambda x: x['change'], reverse=True)


    return top_increase, top_decrease


