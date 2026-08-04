# Generated manually for PurchaseHistory model

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
        ("market", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PurchaseHistory",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "price_paid",
                    models.DecimalField(decimal_places=2, max_digits=12),
                ),
                (
                    "purchased_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "component",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="market.componentpowerlevel",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="purchase_histories",
                        to="accounts.profile",
                    ),
                ),
            ],
            options={
                "ordering": ["-purchased_at"],
            },
        ),
    ]
