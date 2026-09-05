from django.conf import settings


class RobotsHeaderMiddleware:
    """Keep non-production environments out of search indexes."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.ROBOTS_NOINDEX and "X-Robots-Tag" not in response:
            response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response
