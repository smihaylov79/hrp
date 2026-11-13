"""Download exchange rates (EUR -> every non-pegged currency) and store them.

    python manage.py fetch_rates                 # today's rates  (schedule this daily on PythonAnywhere)
    python manage.py fetch_rates --date 2026-10-28
    python manage.py fetch_rates --backfill      # rates for the dates of existing purchases/incomes that
                                                 # have no rate close enough (see audit_rates)
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from reports.rates import RateFetchError, audit, fetch_and_store, foreign_currencies


class Command(BaseCommand):
    help = "Fetch and store exchange rates for today, a given date, or all dates that lack a rate."

    def add_arguments(self, parser):
        parser.add_argument("--date", help="YYYY-MM-DD (default: today)")
        parser.add_argument("--backfill", action="store_true",
                            help="fetch rates for purchase/income dates reported by audit_rates")

    def handle(self, *args, **options):
        if not foreign_currencies():
            self.stdout.write("No currencies need a downloaded rate.")
            return

        if options["backfill"]:
            days = sorted({(currency, day) for _problem, currency, day, _n, _detail in audit()})
        else:
            try:
                day = date.fromisoformat(options["date"]) if options["date"] else date.today()
            except ValueError:
                raise CommandError("--date must be YYYY-MM-DD")
            days = [(None, day)]

        failed = 0
        for currency, day in days:
            try:
                stored = fetch_and_store(day, [currency] if currency else None)
            except RateFetchError as exc:
                failed += 1
                self.stderr.write(self.style.ERROR(str(exc)))
                continue
            for rate in stored:
                self.stdout.write(f"{rate.date_extracted}  {rate.base_currency} -> {rate.target_currency}  {rate.rate}")
        if not days:
            self.stdout.write("Nothing to backfill: every record has a rate.")
        if failed:
            raise CommandError(f"{failed} rate(s) could not be fetched")
