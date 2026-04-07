# Generated manually — adds apartment field to Profile

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_remove_emailverificationtoken_users_email_token_76af91_idx_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='apartment',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
    ]
