from uuid import uuid4

from django.db import models
from django.utils import timezone

class TimeStamped(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True



class NumberedDocument(TimeStamped):
    number = models.CharField(max_length=32, unique=True, blank=True)

    class Meta:
        abstract = True

    def ensure_number(self, prefix: str):
        if not self.number:
            stamp = timezone.localtime().strftime("%Y%m%d")
            self.number = f"{prefix}-{stamp}-{uuid4().hex[:6].upper()}"


