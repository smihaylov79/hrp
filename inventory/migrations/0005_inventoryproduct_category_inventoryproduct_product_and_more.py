# Generated by Django 5.2.1 on 2025-05-23 17:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0004_remove_inventoryproduct_category'),
        ('shopping', '0004_shop_shopping_shoppingproduct'),
    ]

    operations = [
        migrations.AddField(
            model_name='inventoryproduct',
            name='category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_category', to='shopping.productcategory'),
        ),
        migrations.AddField(
            model_name='inventoryproduct',
            name='product',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inventory_product', to='shopping.product'),
        ),
        migrations.AddField(
            model_name='userproductcategory',
            name='product_category',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='user_product_category', to='shopping.productcategory'),
        ),
    ]
