"""One-off data cleanup (IMPROVEMENT_PLAN.md, Phase 8). Safe to run more than once.

    python manage.py cleanup_data --dry-run     # only report what would change
    python manage.py cleanup_data               # do it

1. Duplicate inventory rows: one row per owner + product is kept (the oldest); quantities and amounts are added
   up and inflation-basket items are re-pointed. Caused by the old "product changed category" bug (fixed in Phase 7).
2. Exchange-rate rows that are never read: same-currency rows and BGN <-> EUR rows (the peg is a constant now).
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F, Q

from inventory.dedupe import merge_duplicates
from inventory.models import HouseholdInventoryProduct, InventoryProduct
from reports.currency import PEGGED, clear_cache
from reports.models import ExchangeRate


def unneeded_rates():
    """Rates the conversion code never looks at: X -> X, and BGN <-> EUR in either direction."""
    return ExchangeRate.objects.filter(
        Q(base_currency=F('target_currency')) | Q(base_currency__in=PEGGED, target_currency__in=PEGGED))


class Command(BaseCommand):
    help = "Merge duplicate inventory rows and delete exchange-rate rows that are never used."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='report only, change nothing')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix = '[dry run] would ' if dry_run else ''

        with transaction.atomic():
            merges = []
            for model, owner_field, label in [(HouseholdInventoryProduct, 'household', 'household'),
                                              (InventoryProduct, 'user', 'user')]:
                for merge in merge_duplicates(model, owner_field, dry_run=dry_run):
                    merges.append(merge)
                    self.stdout.write(
                        f"{prefix}merge inventory rows of {label} #{merge['owner']} for \"{merge['product']}\": "
                        f"keep row {merge['kept']}, remove {merge['removed']} "
                        f"(quantity {merge['quantity']}, amount {merge['amount']})")

            rates = unneeded_rates()
            rate_count = rates.count()
            total = ExchangeRate.objects.count()
            if rate_count:
                self.stdout.write(f"{prefix}delete {rate_count} of {total} exchange-rate rows "
                                  f"(same currency or BGN <-> EUR; never read)")
                if not dry_run:
                    ExchangeRate.objects.filter(pk__in=list(rates.values_list('pk', flat=True))).delete()
                    clear_cache()

        if not merges and not rate_count:
            self.stdout.write(self.style.SUCCESS('Nothing to clean up.'))
        elif dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing was changed.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Done: {len(merges)} duplicate group(s) merged, {rate_count} exchange-rate row(s) deleted.'))
