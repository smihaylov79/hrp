"""Helpers for removing the old ``finance`` app's tables from the database (IMPROVEMENT_PLAN.md, Phase 8).

The app itself is gone from the code; its tables stay in MySQL until they are dumped, the dump is checked, and
only then dropped. Used by the commands dump_finance_tables, verify_finance_dump and drop_finance_tables.
"""
import glob
import json
import os
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.db import connection

PREFIX = 'finance_'


def finance_tables():
    """Names of the finance tables that exist in the site's database."""
    with connection.cursor() as cursor:
        cursor.execute("SHOW TABLES LIKE %s", [PREFIX.replace('_', r'\_') + '%'])
        return sorted(row[0] for row in cursor.fetchall())


def row_counts(tables, database=None):
    counts = {}
    with connection.cursor() as cursor:
        for table in tables:
            name = f'`{database}`.`{table}`' if database else f'`{table}`'
            cursor.execute(f'SELECT COUNT(*) FROM {name}')
            counts[table] = cursor.fetchone()[0]
    return counts


def find_binary(name):
    """Full path of a MySQL client program (mysqldump / mysql), or None."""
    found = shutil.which(name)
    if found:
        return found
    for pattern in (r'C:\Program Files\MySQL\MySQL Server *\bin', r'C:\Program Files\MySQL\MySQL Workbench *'):
        for folder in sorted(glob.glob(pattern), reverse=True):
            candidate = Path(folder) / f'{name}.exe'
            if candidate.exists():
                return str(candidate)
    return None


def client_args():
    """Connection arguments for the MySQL client programs; the password travels in the environment."""
    db = settings.DATABASES['default']
    args = ['-h', db.get('HOST') or 'localhost', '-u', db['USER']]
    if db.get('PORT'):
        args += ['-P', str(db['PORT'])]
    env = dict(os.environ, MYSQL_PWD=db.get('PASSWORD') or '')
    return args, env


def run_client(program, arguments, **kwargs):
    args, env = client_args()
    return subprocess.run([program, *args, *arguments], env=env, capture_output=True, **kwargs)


def counts_file(dump_file):
    return Path(str(dump_file) + '.counts.json')


def read_counts(dump_file):
    path = counts_file(dump_file)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def inspect_dump(dump_file, tables):
    """Problems that make a dump file unusable as a backup of ``tables`` (empty list = looks complete)."""
    path = Path(dump_file)
    if not path.is_file():
        return [f'{path} does not exist']
    size = path.stat().st_size
    if size == 0:
        return [f'{path} is empty']
    problems = []
    with open(path, 'rb') as handle:
        handle.seek(max(size - 400, 0))
        if b'Dump completed' not in handle.read():
            problems.append('the file does not end with "Dump completed" - the dump was cut short')
    wanted = {f'CREATE TABLE `{table}`'.encode() for table in tables}
    with open(path, 'rb') as handle:
        for line in handle:
            if line.startswith(b'CREATE TABLE'):
                wanted.discard(line.split(b' (')[0].strip())
                if not wanted:
                    break
    problems += [f'missing in the dump: {name.decode()}' for name in sorted(wanted)]
    return problems
