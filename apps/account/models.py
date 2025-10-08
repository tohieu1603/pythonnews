from django.conf import settings
from django.db import models


class SocialAccount(models.Model):
    PROVIDER_GOOGLE = "google"

    provider = models.CharField(max_length=50)
    sub = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="social_accounts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("provider", "sub")

    def __str__(self) -> str:
        return f"{self.provider}:{self.sub} -> {getattr(self.user, 'email', '')}"
