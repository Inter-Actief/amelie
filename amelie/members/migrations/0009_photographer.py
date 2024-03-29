# Generated by Django 2.2.25 on 2022-04-04 19:45

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0008_auto_20220113_2330'),
    ]

    operations = [
        migrations.CreateModel(
            name='Photographer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(blank=True, max_length=50, null=True, verbose_name='First name')),
                ('last_name_prefix', models.CharField(blank=True, max_length=25, null=True, verbose_name='Last name pre-fix')),
                ('last_name', models.CharField(blank=True, max_length=50, null=True, verbose_name='Last name')),
                ('person', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='members.Person')),
            ],
        ),
    ]
