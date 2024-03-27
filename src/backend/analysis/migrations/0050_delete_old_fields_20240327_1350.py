from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analysis', '0049_auto_20240327_1144'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='datasetanalysis',
            constraint=models.UniqueConstraint(fields=('analysis', 'dataset'), name='uni_dsa_anadsets'),
        ),

        migrations.RemoveField(
            model_name='analysisdsinputfile',
            name='analysis',
        ),
        migrations.RemoveField(
            model_name='analysisdsinputfile',
            name='analysisdset',
        ),
        migrations.AddConstraint(
            model_name='analysisdsinputfile',
            constraint=models.UniqueConstraint(fields=('analysisset', 'sfile'), name='uni_anaset_infile'),
        ),
    ]
