# Generated by Django 4.2.11 on 2024-04-14 16:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0010_auto_20221031_2218'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activity',
            name='components',
            field=models.ManyToManyField(blank=True, to='activities.activity'),
        ),
    ]
