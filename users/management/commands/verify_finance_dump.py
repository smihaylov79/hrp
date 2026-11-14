"""Step 2 of removing the finance tables: prove the dump can be restored.

    python manage.py verify_finance_dump --dump-file ~/finance_tables_prod.sql --database 'user$finance_check'

Loads the dump into a SEPARATE, scratch database and compares the row count of every table with the live
tables. The scratch database must already exist and be empty (on PythonAnywhere create it in the Databases tab);
locally add --create-database, and --drop-database-after to remove it again when the check has passed.
"""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from users.finance_removal import finance_tables, find_binary, inspect_dump, read_counts, row_counts, run_client


class Command(BaseCommand):
    help = "Load a finance dump into a scratch database and compare row counts with the live tables."

    def add_arguments(self, parser):
        parser.add_argument('--dump-file', required=True)
        parser.add_argument('--database', required=True, help='name of the scratch database (never the site database)')
        parser.add_argument('--create-database', action='store_true', help='create the scratch database first')
        parser.add_argument('--drop-database-after', action='store_true',
                            help='drop the scratch database when the check has passed')
        parser.add_argument('--mysql', help='path of the mysql client program (found automatically if omitted)')

    def handle(self, *args, **options):
        scratch, dump_file = options['database'], options['dump_file']
        site_database = settings.DATABASES['default']['NAME']
        if scratch.lower() == site_database.lower():
            raise CommandError('--database must be a scratch database, not the database of the site.')
        if '`' in scratch:
            raise CommandError('Invalid database name.')

        tables = finance_tables()
        expected = row_counts(tables) if tables else read_counts(dump_file)
        if not expected:
            raise CommandError('There are no finance tables to compare with and no <dump>.counts.json file.')
        problems = inspect_dump(dump_file, list(expected))
        if problems:
            raise CommandError('The dump is not complete: ' + '; '.join(problems))
        program = options['mysql'] or find_binary('mysql')
        if not program:
            raise CommandError('The mysql client was not found; pass its path with --mysql')

        with connection.cursor() as cursor:
            if options['create_database']:
                cursor.execute(f'CREATE DATABASE IF NOT EXISTS `{scratch}` CHARACTER SET utf8mb4')
            cursor.execute('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = %s', [scratch])
            if cursor.fetchone()[0]:
                raise CommandError(f'The scratch database {scratch} is not empty; use an empty one.')

        with open(dump_file, 'rb') as handle:
            result = run_client(program, ['--default-character-set=utf8mb4', scratch], stdin=handle)
        if result.returncode != 0:
            raise CommandError(f'Loading the dump failed (exit {result.returncode}): '
                               f'{result.stderr.decode(errors="replace")[:500]}')

        restored = row_counts(list(expected), database=scratch)
        different = {table: (expected[table], restored.get(table)) for table in expected
                     if restored.get(table) != expected[table]}
        for table in expected:
            self.stdout.write(f'  {table:42} live {expected[table]:>10}   restored {restored.get(table):>10}')
        if different:
            raise CommandError(f'Row counts differ (live, restored): {different}')

        if options['drop_database_after']:
            with connection.cursor() as cursor:
                cursor.execute(f'DROP DATABASE `{scratch}`')
            self.stdout.write(f'Scratch database {scratch} dropped.')
        self.stdout.write(self.style.SUCCESS(
            f'The dump restores correctly: {len(expected)} tables, {sum(expected.values())} rows match.'))
