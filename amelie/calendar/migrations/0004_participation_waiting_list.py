# Generated by Django 2.2.25 on 2022-02-10 22:35

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('calendar', '0003_auto_20220207_1939'),
    ]

    operations = [
        migrations.AddField(
            model_name='participation',
            name='waiting_list',
            field=models.BooleanField(default=False, verbose_name='On waiting list'),
        ),
    ]
