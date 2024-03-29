# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-25 22:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('files', '0001_initial'),
        ('members', '0001_initial'),
        ('activities', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NewsItem',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('publication_date', models.DateTimeField(auto_now_add=True)),
                ('title_nl', models.CharField(max_length=150)),
                ('title_en', models.CharField(blank=True, max_length=175, null=True)),
                ('slug', models.SlugField(editable=False)),
                ('introduction_nl', models.CharField(max_length=175)),
                ('introduction_en', models.CharField(blank=True, max_length=175, null=True)),
                ('content_nl', models.TextField()),
                ('content_en', models.TextField(blank=True)),
                ('pinned', models.BooleanField(default=False, help_text='Choose this option to pin the news item')),
                ('activities', models.ManyToManyField(blank=True, to='activities.Activity')),
                ('attachments', models.ManyToManyField(blank=True, to='files.Attachment')),
                ('author', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='members.Person')),
                ('publisher', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='members.Committee')),
            ],
            options={
                'verbose_name': 'News message',
                'ordering': ['-publication_date'],
                'verbose_name_plural': 'News messages',
            },
        ),
    ]
