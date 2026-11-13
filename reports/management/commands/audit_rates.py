"""List purchases / incomes in a foreign currency that have no usable exchange rate.

    python manage.py audit_rates

Read-only. BGN and EUR never need a rate (fixed peg). Fix what it reports with `fetch_rates --backfill`.
"""
from django.core.management.base import BaseCommand

from reports.rates import audit, used_foreign_dates


class Command(BaseCommand):
    help = "Report currency/date combinations used in shopping or income that have no (or only an old) rate."

    def add_arguments(self, parser):
        parser.add_argument("--max-age", type=int, default=4,
                            help="a rate older than this many days counts as stale (default 4)")

    def handle(self, *args, **options):
        used = used_foreign_dates()
        problems = audit(options["max_age"])
        self.stdout.write(f"{sum(used.values())} record(s) in foreign currencies on {len(used)} date(s).")
        if not problems:
            self.stdout.write(self.style.SUCCESS("Every record has an exchange rate for its date."))
            return
        for problem, currency, day, records, detail in problems:
            style = self.style.ERROR if problem == "missing" else self.style.WARNING
            self.stdout.write(style(f"{problem:8} {currency}  {day}  {records} record(s)  {detail}"))
        self.stdout.write(f"{len(problems)} problem(s). Run: python manage.py fetch_rates --backfill")
