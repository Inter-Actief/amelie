# Generated by Django 2.2.25 on 2021-12-11 20:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('education', '0002_auto_20201103_2220'),
    ]

    operations = [
        migrations.AddField(
            model_name='complaintcomment',
            name='official',
            field=models.BooleanField(default=False, verbose_name='Comment by Education Committee'),
        ),
    ]
