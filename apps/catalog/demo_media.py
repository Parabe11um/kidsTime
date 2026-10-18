"""Local copies of the six legacy demo covers; no runtime CDN requests."""

from urllib.parse import urlsplit

from django.templatetags.static import static


DEMO_COVER_IMAGES = {
    "/photo-1446776811953-b23d57bd21aa": "images/demo/space.jpg",
    "/photo-1500530855697-b586d89ba3ee": "images/demo/nature.jpg",
    "/photo-1474511320723-9a56873867b5": "images/demo/fox.jpg",
    "/photo-1532094349884-543bc11b234d": "images/demo/science.jpg",
    "/photo-1503454537195-1dcabb73ffb9": "images/demo/family.jpg",
    "/photo-1542810634-71277d95dcbb": "images/demo/park.jpg",
}


def resolve_demo_cover_url(url):
    """Recognize existing demo URLs without changing stored or uploaded images."""
    if not url:
        return url
    try:
        parsed = urlsplit(url)
    except ValueError:
        return url
    if parsed.scheme in ("http", "https") and parsed.hostname == "images.unsplash.com":
        asset = DEMO_COVER_IMAGES.get(parsed.path)
        if asset:
            return static(asset)
    return url
