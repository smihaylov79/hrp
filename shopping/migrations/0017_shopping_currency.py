# Generated by Django 5.2.1 on 2025-07-20 10:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shopping', '0016_remove_product_available_stock_remove_product_price_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='shopping',
            name='currency',
            field=models.CharField(choices=[('BGN', 'BG Lev'), ('EUR', 'Euro'), ('USD', 'US Dollar'), ('GBP', 'GB Pound')], default='BGN', max_length=3),
        ),
    ]
