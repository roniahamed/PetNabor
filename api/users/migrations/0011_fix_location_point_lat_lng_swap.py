"""
Data migration: Fix swapped latitude/longitude in profile location_point.

Previously, coordinates were stored as Point(latitude, longitude) due to a bug
in validate_location_point. PostGIS expects Point(longitude, latitude) i.e. Point(x=lng, y=lat).

This migration uses PostGIS ST_MakePoint to swap x and y for all existing records.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0010_profile_apartment"),
    ]

    operations = [
        migrations.RunSQL(
            # Forward: swap x and y (fix lat/lng swap)
            sql="""
                UPDATE users_profile
                SET location_point = ST_SetSRID(
                    ST_MakePoint(
                        ST_Y(location_point),
                        ST_X(location_point)
                    ),
                    4326
                )
                WHERE location_point IS NOT NULL;
            """,
            # Reverse: swap back (undo the fix)
            reverse_sql="""
                UPDATE users_profile
                SET location_point = ST_SetSRID(
                    ST_MakePoint(
                        ST_Y(location_point),
                        ST_X(location_point)
                    ),
                    4326
                )
                WHERE location_point IS NOT NULL;
            """,
        ),
    ]
