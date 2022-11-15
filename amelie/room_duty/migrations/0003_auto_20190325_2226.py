# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-25 21:26
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('room_duty', '0002_custom_pools'),
    ]

    operations = [
        migrations.CreateModel(
            name='BalconyDutyAssociation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('association', models.CharField(max_length=255, verbose_name='Association')),
                ('is_this_association', models.BooleanField(verbose_name='Is Inter-Actief')),
                ('rank', models.PositiveIntegerField(unique=True)),
            ],
            options={
                'ordering': ['rank'],
            },
        ),
        migrations.AddField(
            model_name='roomdutytable',
            name='balcony_duty',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='room_duty.BalconyDutyAssociation'),
        ),
    ]