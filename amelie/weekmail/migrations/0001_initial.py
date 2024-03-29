# -*- coding: utf-8 -*-
# Generated by Django 1.11.16 on 2019-03-25 22:00
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('members', '0001_initial'),
        ('news', '0001_initial'),
        ('calendar', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WeekMail',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('published', models.BooleanField(default=False)),
                ('status', models.CharField(choices=[('N', 'Not yet sent'), ('U', 'Currently sending'), ('V', 'Sent'), ('E', 'Error during sending')], default='N', max_length=1)),
                ('creation_date', models.DateTimeField(auto_now=True)),
                ('mailtype', models.CharField(choices=[('W', 'Weekly mail'), ('M', 'Mastermail')], default='W', max_length=1, verbose_name='Type of mailing')),
            ],
        ),
        migrations.CreateModel(
            name='WeekMailNewsArticle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title_nl', models.CharField(max_length=150)),
                ('title_en', models.CharField(max_length=150)),
                ('content_nl', models.TextField()),
                ('content_en', models.TextField()),
            ],
        ),
        migrations.AddField(
            model_name='weekmail',
            name='added_news_articles',
            field=models.ManyToManyField(blank=True, to='weekmail.WeekMailNewsArticle'),
        ),
        migrations.AddField(
            model_name='weekmail',
            name='new_activities',
            field=models.ManyToManyField(blank=True, related_name='new_activities', to='calendar.Event', verbose_name='new events'),
        ),
        migrations.AddField(
            model_name='weekmail',
            name='news_articles',
            field=models.ManyToManyField(blank=True, to='news.NewsItem', verbose_name='news articles'),
        ),
        migrations.AddField(
            model_name='weekmail',
            name='writer',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='members.Person'),
        ),
    ]
