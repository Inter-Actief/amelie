# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-25 22:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('members', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attachment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file', models.FileField(upload_to='uploads/%Y/%m/%d')),
                ('caption', models.CharField(blank=True, max_length=150, null=True)),
                ('thumb_small', models.ImageField(blank=True, editable=False, height_field='thumb_small_height', null=True, upload_to='uploads/%Y/%m/%d', width_field='thumb_small_width')),
                ('thumb_medium', models.ImageField(blank=True, editable=False, height_field='thumb_medium_height', null=True, upload_to='uploads/%Y/%m/%d', width_field='thumb_medium_width')),
                ('thumb_large', models.ImageField(blank=True, editable=False, height_field='thumb_large_height', null=True, upload_to='uploads/%Y/%m/%d', width_field='thumb_large_width')),
                ('mimetype', models.CharField(editable=False, max_length=75)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('modified', models.DateTimeField(auto_now=True)),
                ('thumb_small_height', models.IntegerField(editable=False, null=True)),
                ('thumb_small_width', models.IntegerField(editable=False, null=True)),
                ('thumb_medium_height', models.IntegerField(editable=False, null=True)),
                ('thumb_medium_width', models.IntegerField(editable=False, null=True)),
                ('thumb_large_height', models.IntegerField(editable=False, null=True)),
                ('thumb_large_width', models.IntegerField(editable=False, null=True)),
                ('public', models.BooleanField(default=False)),
                ('owner', models.ForeignKey(editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='members.Person')),
            ],
            options={
                'verbose_name': 'Appendix',
                'ordering': ['file'],
                'verbose_name_plural': 'Attachments',
            },
        ),
    ]
