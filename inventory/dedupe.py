"""Merging duplicate inventory rows.

There must be one inventory row per owner and product. Before Phase 7 a purchase looked the row up by owner +
product + category, so changing a product's category created a second row. ``merge_duplicates`` folds such rows
into the oldest one. It takes the model class as an argument so that it works both with the real models (the
``cleanup_data`` command) and with the historical models inside a migration.
"""
from decimal import Decimal

from django.db.models import Count


def duplicate_groups(model, owner_field):
    """[(owner id, product id, number of rows)] for every owner + product that has more than one row."""
    groups = (model.objects.exclude(product__isnull=True)
              .values(f'{owner_field}_id', 'product_id').annotate(rows=Count('id')).filter(rows__gt=1)
              .order_by(f'{owner_field}_id', 'product_id'))
    return [(group[f'{owner_field}_id'], group['product_id'], group['rows']) for group in groups]


def merge_duplicates(model, owner_field, dry_run=False):
    """Merge duplicate rows of ``model`` (owner in ``owner_field``: "user" or "household").

    The oldest row is kept. Quantities and amounts are added up, the average price is recalculated, the larger
    daily consumption / minimum quantity wins, the category follows the product, and every row that pointed to a
    removed duplicate (inflation basket items) is re-pointed to the kept row first.

    Returns a list of dicts describing each merge. Running it again finds nothing: it is idempotent.
    """
    report = []
    for owner_id, product_id, _rows in duplicate_groups(model, owner_field):
        rows = list(model.objects.filter(**{f'{owner_field}_id': owner_id, 'product_id': product_id})
                    .select_related('product').order_by('id'))
        keeper, extras = rows[0], rows[1:]
        quantity = sum((Decimal(str(row.quantity)) for row in rows), Decimal('0'))
        amount = sum((Decimal(str(row.amount)) for row in rows), Decimal('0'))
        report.append({
            'owner': owner_id, 'product': keeper.product.name, 'kept': keeper.pk, 'removed': [row.pk for row in extras],
            'quantity': quantity, 'amount': amount,
        })
        if dry_run:
            continue

        keeper.quantity = quantity
        keeper.amount = amount
        keeper.average_price = (amount / quantity).quantize(Decimal('0.01')) if quantity > 0 else Decimal('0.00')
        keeper.daily_consumption = max(row.daily_consumption for row in rows)
        keeper.minimum_quantity = max(row.minimum_quantity for row in rows)
        keeper.inventory_related = any(row.inventory_related for row in rows)
        keeper.category_id = keeper.product.category_id
        keeper.save()

        extra_ids = [row.pk for row in extras]
        for relation in model._meta.related_objects:          # e.g. inflation basket items
            related, field = relation.related_model, relation.field.name
            related.objects.filter(**{f'{field}__in': extra_ids}).update(**{field: keeper})
            # the same basket may now list the kept row twice: keep one entry per basket
            other_fields = [f.name for f in related._meta.fields if f.name not in ('id', field) and f.is_relation]
            seen = set()
            for item in related.objects.filter(**{field: keeper}).order_by('id'):
                key = tuple(getattr(item, f'{name}_id') for name in other_fields)
                if key in seen:
                    item.delete()
                seen.add(key)
        model.objects.filter(pk__in=extra_ids).delete()
    return report
