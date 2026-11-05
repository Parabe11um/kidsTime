# Day route: origin and travel times

Reference: the supplied `Route.png` desktop layout (1440px). The route keeps the
1000px content width, a 356px summary, numbered cards and time badges beside the
dashed connections. The browser-storage note sits separately below the summary.
The existing phone and tablet layouts remain responsive.

## User flow

- Walking is the default. The selector also offers driving and public transport;
  the estimate and the external Yandex Maps link use the same mode and point order.
- The visible location button requests browser geolocation only when clicked.
  Permission denial, unavailable position and approximate coordinates have explicit
  feedback. An existing origin is retained if a later location attempt fails.
- The origin chooser supports a map click, marker dragging, geolocation, an address
  search when available, and a keyboard-accessible coordinate form. A preview must
  be confirmed; cancelling leaves the previous origin intact. The map's initial
  camera position is never silently accepted as the origin.
- Up to nine catalog places can be selected, plus an optional origin. The count is
  the actual number of selected catalog places, excluding the origin.
- Changing the origin, mode or place order invalidates old estimates immediately.
  Stale responses cannot replace a newer route. The complete route uses one provider
  request, with optimization disabled. Server-returned legs keep their point IDs.
- Without an origin, times are calculated only between catalog places. The first
  connection offers origin selection. Failed legs do not receive guessed durations.
  Links to the corresponding leg in Yandex Maps remain available.
- Times describe travel at the moment of calculation; event visits and waiting at
  activities are not included. They are not a schedule of arrival at booked sessions.

## Configuration

The existing `YANDEX_MAPS_API_KEY` provides the map picker. The additional products
are opt-in; nothing is purchased or activated by this change. Set keys only in the
server environment, never in Git or a chat message:

```dotenv
# JavaScript API: existing public, HTTP-Referer-restricted map key.
YANDEX_MAPS_API_KEY=
# Route Details HTTP API: required to display minutes between points.
YANDEX_ROUTER_API_KEY=
# HTTP Geocoder: optional address search and readable origin addresses.
YANDEX_GEOCODER_API_KEY=
```

Router and geocoder keys stay server-side and must have access to their respective
products. A JavaScript API key alone does not imply this access. Check the connected
products and available quota in the Yandex developer account before enabling them.
After changing production environment values, recreate `web` with the existing
production Compose command. No Compose changes or database migration are required.

Without the router key, the page offers Yandex Maps links instead of invented
minutes. Without the geocoder key, map selection, browser geolocation and explicit
coordinates still work. If the map cannot load, the coordinate form remains usable.

Official integration references:

- https://yandex.ru/maps-api/docs/router-api/request.html
- https://yandex.ru/maps-api/docs/router-api/response.html
- https://yandex.ru/maps-api/docs/geocoder-api/request.html
- https://yandex.ru/maps-api/docs/geocoder-api/response.html

## Requests and temporary data

Both `/events/api/walk/times/` and `/events/api/walk/geocode/` accept CSRF-protected
JSON POST requests, with a 4096-byte body limit. Coordinates are not URL parameters
of KidsTime requests. Responses carry `Cache-Control: no-store`. Provider errors
are reduced to generic codes; private keys and provider request URLs are not logged.
Routing accepts only currently public catalog events with published, located venues.
If the selection has changed, the client reloads its public event list.

The existing shared database limiter caps each operation at 20 requests per hour
per client IP, across all Gunicorn workers. Repeated whole-route calculations use
a five-minute cache in the page's memory (maximum 20 entries). The refresh action
requests a new estimate. No provider responses or coordinates are saved in browser
storage, accounts or route records. Clearing the origin also clears that memory cache.
Saved routes continue to hold their names, catalog IDs and real creation dates.

## Verification

Service tests cover response units, point order, partial failures, malformed data,
timeouts and key redaction. Endpoint tests cover publication/coordinate validation,
CSRF, rate limits, missing configuration and server-only keys. Browser tests cover
nine widths from 320 to 1920px, map/address/geolocation selection, denial and cancel,
mode changes, reordered stops, persistence of IDs, stale responses and API failures.
External services are simulated in these tests; no production key or billed request
was used during implementation. Live activation requires a configured service key.
