# Generated by Django 5.2.1 on 2025-08-01 11:58

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0007_symbolsmapping_fundamentalsdata'),
    ]

    operations = [
        migrations.AlterField(
            model_name='symbolsmapping',
            name='official_symbol',
            field=models.CharField(blank=True, max_length=25, null=True),
        ),
    ]
