"""Step 3 of removing the finance tables: drop them. IRREVERSIBLE - needs a complete, current dump.

    python manage.py drop_finance_tables --dump-file ~/finance_tables_prod.sql --dry-run
    python manage.py drop_finance_tables --dump-file ~/finance_tables_prod.sql --optimize

Refuses to do anything unless the dump file (made by dump_finance_tables) is complete, contains every finance
table that exists now, and its recorded row counts equal the live row counts. Then it:
  1. drops the finance_* tables,
  2. deletes the finance rows from django_migrations,
  3. removes the content types (and their permissions) of apps that are no longer installed
     (manage.py remove_stale_contenttypes --include-stale-apps),
  4. with --optimize: runs OPTIMIZE TABLE on the remaining tables.
Running it again when the tables are gone only reports that there is nothing to do.
"""
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from users.finance_removal import finance_tables, inspect_dump, read_counts, row_counts

APP = 'finance'


def stale_app_labels():
    installed = {config.label for config in apps.get_app_configs()}
    return sorted(set(ContentType.objects.values_list('app_label', flat=True)) - installed)


class Command(BaseCommand):
    help = "Drop the finance_* tables after checking the dump; clean migration rows and stale content types."

    def add_arguments(self, parser):
        parser.add_argument('--dump-file', required=True, help='the .sql file written by dump_finance_tables')
        parser.add_argument('--dry-run', action='store_true', help='run all checks and report, change nothing')
        parser.add_argument('--optimize', action='store_true', help='OPTIMIZE TABLE on the remaining tables afterwards')

    def handle(self, *args, **options):
        if apps.is_installed(APP):
            raise CommandError('The finance app is still installed; remove it from INSTALLED_APPS first.')
        dry_run = options['dry_run']
        prefix = '[dry run] would ' if dry_run else ''
        tables = finance_tables()

        if tables:
            # --- the safety gate: no complete and current dump, no drop ------------------------------
            problems = inspect_dump(options['dump_file'], tables)
            if problems:
                raise CommandError('Refusing to drop: ' + '; '.join(problems))
            recorded = read_counts(options['dump_file'])
            if recorded is None:
                raise CommandError('Refusing to drop: the <dump>.counts.json file written by dump_finance_tables '
                                   'is missing next to the dump.')
            live = row_counts(tables)
            if recorded != live:
                changed = sorted(table for table in set(live) | set(recorded) if live.get(table) != recorded.get(table))
                raise CommandError(f'Refusing to drop: the tables changed since the dump was made ({changed}). '
                                   f'Run dump_finance_tables again.')
            self.stdout.write(f'Dump checked: {len(tables)} tables, {sum(live.values())} rows, counts match.')

            self.stdout.write(f'{prefix}drop {len(tables)} tables: {", ".join(tables)}')
            if not dry_run:
                with connection.cursor() as cursor:
                    cursor.execute('SET FOREIGN_KEY_CHECKS = 0')
                    try:
                        for table in tables:
                            cursor.execute(f'DROP TABLE `{table}`')
                    finally:
                        cursor.execute('SET FOREIGN_KEY_CHECKS = 1')
        else:
            self.stdout.write('No finance tables in this database.')

        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM django_migrations WHERE app = %s', [APP])
            migration_rows = cursor.fetchone()[0]
            if migration_rows:
                self.stdout.write(f'{prefix}delete {migration_rows} finance rows from django_migrations')
                if not dry_run:
                    cursor.execute('DELETE FROM django_migrations WHERE app = %s', [APP])

        stale = stale_app_labels()
        if stale:
            count = ContentType.objects.filter(app_label__in=stale).count()
            self.stdout.write(f'{prefix}remove {count} stale content types (apps: {", ".join(stale)}) '
                              f'and their permissions')
            if not dry_run:
                call_command('remove_stale_contenttypes', include_stale_apps=True, interactive=False, verbosity=0)

        if options['optimize']:
            with connection.cursor() as cursor:
                cursor.execute('SHOW TABLES')
                remaining = [row[0] for row in cursor.fetchall() if not row[0].startswith('finance_')]
                self.stdout.write(f'{prefix}OPTIMIZE {len(remaining)} tables')
                if not dry_run:
                    for table in remaining:
                        cursor.execute(f'OPTIMIZE TABLE `{table}`')
                        cursor.fetchall()

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run: nothing was changed.'))
        elif not tables and not migration_rows and not stale:
            self.stdout.write(self.style.SUCCESS('Nothing to do: the finance data is already gone.'))
        else:
            self.stdout.write(self.style.SUCCESS('Finance tables, migration rows and stale content types removed.'))
