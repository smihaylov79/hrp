"""Step 1 of removing the finance tables: dump them to a .sql file.

    python manage.py dump_finance_tables --output ~/finance_tables_prod.sql

Exits with an error (non-zero status) if anything goes wrong, so a deploy script stops here.
Writes <file>.counts.json with the row count of every table next to the dump.
"""
import json

from django.core.management.base import BaseCommand, CommandError

from users.finance_removal import counts_file, finance_tables, find_binary, inspect_dump, row_counts, run_client


class Command(BaseCommand):
    help = "Dump the finance_* tables to a .sql file and check that the file is complete."

    def add_arguments(self, parser):
        parser.add_argument('--output', required=True, help='path of the .sql file to write')
        parser.add_argument('--mysqldump', help='path of the mysqldump program (found automatically if omitted)')

    def handle(self, *args, **options):
        from django.conf import settings

        tables = finance_tables()
        if not tables:
            self.stdout.write(self.style.SUCCESS('There are no finance tables in this database: nothing to dump.'))
            return
        program = options['mysqldump'] or find_binary('mysqldump')
        if not program:
            raise CommandError('mysqldump was not found; pass its path with --mysqldump')

        output = options['output']
        counts = row_counts(tables)
        result = run_client(program, [
            '--single-transaction', '--no-tablespaces', '--default-character-set=utf8mb4',
            f'--result-file={output}', settings.DATABASES['default']['NAME'], *tables])
        if result.returncode != 0:
            raise CommandError(f'mysqldump failed (exit {result.returncode}): '
                               f'{result.stderr.decode(errors="replace")[:500]}')
        problems = inspect_dump(output, tables)
        if problems:
            raise CommandError('The dump is not complete: ' + '; '.join(problems))
        if row_counts(tables) != counts:
            raise CommandError('The finance tables changed while they were dumped; run the command again.')

        counts_file(output).write_text(json.dumps(counts, indent=1), encoding='utf-8')
        for table, rows in counts.items():
            self.stdout.write(f'  {table:42} {rows:>10} rows')
        self.stdout.write(self.style.SUCCESS(
            f'Dumped {len(tables)} tables, {sum(counts.values())} rows to {output}. '
            f'Copy this file somewhere safe before dropping anything.'))
