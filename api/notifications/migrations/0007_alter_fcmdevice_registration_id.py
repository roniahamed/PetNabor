from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0006_alter_notifications_notification_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="fcmdevice",
            name="registration_id",
            field=models.CharField(max_length=500),
        ),
    ]
