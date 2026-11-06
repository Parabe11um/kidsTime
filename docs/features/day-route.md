# Day route: origin and external directions

Reference: the supplied `Route.png` desktop layout (1440px). The route keeps the
1000px content width, a 356px summary and numbered cards with dashed connections.
Travel-time badges, estimates and calculation controls have been removed by product
request. The browser-storage note sits separately below the summary. The existing
phone and tablet layouts remain responsive.

## User flow

- Walking is the default. The selector also offers driving and public transport;
  the external Yandex Maps link uses the selected mode and point order.
- The visible location button requests browser geolocation only when clicked.
  Permission denial, unavailable position and approximate coordinates have explicit
  feedback. An existing origin is retained if a later location attempt fails.
- The origin chooser supports a map click, marker dragging, geolocation, an address
  search when available, and a keyboard-accessible coordinate form. A preview must
  be confirmed; cancelling leaves the previous origin intact. The map's initial
  camera position is never silently accepted as the origin.
- Up to nine catalog places can be selected, plus an optional origin. The count is
  the actual number of selected catalog places, excluding the origin.
- Changing the origin, mode or place order updates the external directions link.
  Opening, editing, saving or clearing a route never requests travel-time estimates.
  This also applies when a router API key is configured on the server.
- The page has no duration totals, per-leg time placeholders or refresh button.
  Directions are opened in Yandex Maps using the main route button.

## Configuration

The existing `YANDEX_MAPS_API_KEY` provides the map picker. The additional products
are opt-in; nothing is purchased or activated by this change. Set keys only in the
server environment, never in Git or a chat message:

```dotenv
# JavaScript API: existing public, HTTP-Referer-restricted map key.
YANDEX_MAPS_API_KEY=
# HTTP Geocoder: optional address search and readable origin addresses.
YANDEX_GEOCODER_API_KEY=
```

The geocoder key stays server-side and must have access to its respective product.
A JavaScript API key alone does not imply this access. Check the connected product
and available quota in the Yandex developer account before enabling it.
After changing production environment values, recreate `web` with the existing
production Compose command. No Compose changes or database migration are required.

No router key is needed for the current page. Without the geocoder key, map
selection, browser geolocation and explicit coordinates still work. If the map
cannot load, the coordinate form remains usable.

Official integration references:

- https://yandex.ru/maps-api/docs/geocoder-api/request.html
- https://yandex.ru/maps-api/docs/geocoder-api/response.html

## Requests and temporary data

The page uses `/events/api/walk/geocode/` only for enabled address lookup. It accepts
CSRF-protected JSON POST requests, with a 4096-byte body limit. Coordinates are not
URL parameters of KidsTime requests. Responses carry `Cache-Control: no-store`.
Provider errors are reduced to generic codes; private keys and provider request
URLs are not logged.

The existing shared database limiter caps geocoding at 20 requests per hour per
client IP, across all Gunicorn workers. No provider responses or origin coordinates
are saved in browser storage, accounts or route records. Saved routes continue to
hold their names, catalog IDs and real creation dates.

The separately tested `/events/api/walk/times/` backend and its optional
`YANDEX_ROUTER_API_KEY` setting remain available for a future integration, but the
page no longer exposes its URL or calls it. Leaving this setting empty disables the
backend provider as well. Restoring travel-time UI requires a separate product change.

## Verification

Service tests cover response units, point order, partial failures, malformed data,
timeouts and key redaction. Endpoint tests cover publication/coordinate validation,
CSRF, rate limits, missing configuration and server-only keys. Browser tests cover
nine widths from 320 to 1920px, map/address/geolocation selection, denial and cancel,
mode changes, reordered stops and persistence of IDs. They also check that no time
badges or totals appear and no routing requests are made during these interactions,
including with router configuration present. External services are simulated in
these tests; no production key or billed request is used.
