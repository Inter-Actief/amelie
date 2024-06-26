# Generated by Django 3.2.21 on 2024-06-12 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('weekmail', '0003_alter_weekmail_mailtype'),
    ]

    operations = [
        migrations.AlterField(
            model_name='weekmail',
            name='mailtype',
            field=models.CharField(choices=[('W', 'Weekly mail'), ('M', 'Mastermail'), ('E', 'Educational mail'), ('A', 'Active members mail')], default='W', max_length=1, verbose_name='Type of mailing'),
        ),
    ]
