# Generated by Django 5.2.1 on 2025-07-26 21:24

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0002_householdinflationbasket_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='householdinflationbasket',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='householdinflationbasketitem',
            name='basket',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='household_basket_items', to='reports.householdinflationbasket'),
        ),
        migrations.AlterField(
            model_name='userinflationbasket',
            name='name',
            field=models.CharField(max_length=100, unique=True),
        ),
        migrations.AlterField(
            model_name='userinflationbasketitem',
            name='basket',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_basket_items', to='reports.userinflationbasket'),
        ),
    ]
