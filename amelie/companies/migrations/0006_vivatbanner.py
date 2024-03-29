# Generated by Django 3.2.17 on 2023-05-23 14:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0005_add_default_career_label'),
    ]

    operations = [
        migrations.CreateModel(
            name='VivatBanner',
            fields=[
                ('basebanner_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='companies.basebanner')),
                ('url', models.URLField()),
                ('views', models.PositiveIntegerField(default=0, editable=False)),
            ],
            options={
                'verbose_name': 'I/O Vivat banner',
                'verbose_name_plural': 'I/O Vivat banners',
                'ordering': ['-end_date'],
            },
            bases=('companies.basebanner',),
        ),
    ]
