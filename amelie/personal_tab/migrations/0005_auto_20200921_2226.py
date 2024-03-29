# -*- coding: utf-8 -*-
# Generated by Django 1.11.29 on 2020-09-21 20:26
from __future__ import unicode_literals

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal_tab', '0004_new_personal_tab'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authorization',
            name='account_holder_name',
            field=models.CharField(blank=True, max_length=70, validators=[django.core.validators.RegexValidator(message='Only alphanumerical signs are allowed', regex="^[a-zA-Z0-9-?:().,\\'+ ]*$")], verbose_name='account holder'),
        ),
        migrations.AlterField(
            model_name='debtcollectioninstruction',
            name='description',
            field=models.CharField(max_length=140, validators=[django.core.validators.RegexValidator(message='Only alphanumerical signs are allowed', regex="^[a-zA-Z0-9-?:().,\\'+ ]*$")], verbose_name='description'),
        ),
        migrations.AlterField(
            model_name='debtcollectioninstruction',
            name='end_to_end_id',
            field=models.CharField(max_length=35, validators=[django.core.validators.RegexValidator(message='Only alphanumerical signs are allowed', regex="^[a-zA-Z0-9-?:().,\\'+ ]*$")], verbose_name='end-to-end-id'),
        ),
    ]
