# Generated by Django 5.2.1 on 2025-05-23 19:10

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0006_remove_inventoryproduct_name'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='userproductcategory',
            name='name',
        ),
    ]
