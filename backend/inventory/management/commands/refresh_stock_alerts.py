from django.core.management.base import BaseCommand
from inventory.services import refresh_alerts


class Command(BaseCommand):
    help = "Recalcula alertas de estoque e validade."

    def handle(self, *args, **options):
        alerts = refresh_alerts(notify=True)
        self.stdout.write(self.style.SUCCESS(f"{len(alerts)} alertas ativos gerados."))
