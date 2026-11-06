# Release 4 design implementation

The reference is the KidsTime Figma section `791:11637` and the supplied
`KidsTime.zip` export. The archive contains 29 PNGs at the native 402px mobile
screen width, including annotations. It contains no standalone image or SVG assets.

## Implemented in this change

- Initial search guidance, map action and a stack of data-backed event cards.
- A plain favorites heading, compact event cards and query filtering.
- Favorites reload when the saved set changes; removing the final event shows
  the empty state. Older responses cannot overwrite a newer saved selection.
- Both event share buttons use the existing native share/clipboard behavior.
- The organizer website is shown when present in the catalog data.
- Calendar downloads use the next exact, upcoming session and preserve its
  recorded end time or duration. Availability periods do not generate sessions.

## Remaining work

- Separate exports of the favorites heart, authentication artwork, profile action
  icons and error-page illustrations. Full-screen PNGs remain references rather
  than page backgrounds or crops embedded as UI assets.
- Account-owned route storage and synchronization between devices. The route list,
  naming and editing currently use the existing browser storage.
- Subscriptions, notifications and reviews need their actual product behavior
  and data; example ratings, review counts and route times are not production data.
- Desktop family artwork and the footer's exact animation still need source
  artwork/motion references. Adapt new mobile states to desktop as agreed.

Email verification remains in place. Telegram and VK authentication are excluded.


## Desktop export, 31 October 2026

Reference: `KidsTime(1).zip`, 45 PNG exports. Implemented with existing Django
pages, dynamic catalog photographs and the existing SVG wordmark/navigation.

- Shared desktop/tablet header, profile drawer and empty notifications popover;
  navigation uses live favorite and saved-browser-route counts.
- Single-column text search results, sidebar groups, date range and session-time
  controls, and pagination retaining the selected filters.
- Date and time constraints match the same exact session. Availability periods
  without sessions match overlapping dates but never generate clock times.
- Detail gallery thumbnails/tools below the photo; schedule, actions and source
  in a desktop sidebar; recommendations in three columns.
- Desktop favorites grid, footer layout, and full-height two-column email auth.
- Saved routes in this browser: name dialog, list, reopen, reorder, rename, delete,
  a 20-route limit and validation of stored IDs/names. Unpublished places are
  checked against the existing public API on each open; travel times/distances
  are not fabricated. These routes do not sync between devices or accounts.
- Authenticated profile name and marketing-consent settings; user identity comes
  from the session, and the recorded privacy consent is preserved.
- Branded 404/500 states and the original Figma empty-search illustration
  (node `791:11618`, static/illustrations/empty-search.png).

At this stage the outstanding original source assets were the empty-route map, favorites heart,
error-page illustrations, auth background and header/drawer icon set. These are
flattened inside the supplied full-screen PNGs. After one successful asset fetch,
Figma MCP returned its Starter-plan request limit. The existing auth gradient is
retained; notifications currently use a text control in the header. Reference
screenshots are not embedded as page backgrounds or cropped into fake UI assets.

The exported settings/review/subscription screens also refer to functionality
not in the current data model: event-update subscriptions, delivered personal
notifications and review/rating records. No mock review
counts, sample notifications, non-working social buttons or fake subscriptions
are introduced. Telegram/VK login remain excluded; email confirmation is retained.

Validation: browser interaction and overflow checks on 1440, 1024, 834, 402 and
320px; route lifecycle, final favorite removal, dialogs and local-storage errors;
Django filter/pagination/settings tests run in CI. No schema migration is added.

## Mobile export, 1 November 2026

Reference: `KidsTime(2).zip`, 29 native PNG exports. The mobile overrides originally
applied below 768px; the tablet export below now gives 640–1023px its own layout.

- Search hero, result count/map row and 108px compact image cards; title/address
  ellipses and calendar/age/price facts are shared with favorites.
- Profile hero, floating avatar, live collection tiles and expandable name and
  marketing-consent settings. The photo picker uploads to the current account with
  CSRF protection. JPEG/PNG/WebP uploads are limited to 5 MiB and 16 megapixels;
  animations are rejected, metadata is stripped, and the stored JPEG has a random
  filename and a maximum dimension of 512px.
- Plain day-route header, separate point toolbars, compact cards, empty-route map,
  one add-place action and a native bottom-sheet naming dialog. There are no
  invented travel durations, distances or example addresses.
- Optional initial point is obtained only after pressing the location button.
  Coordinates stay in page memory and are passed to Yandex Maps on opening the
  route. They are not saved in route records or browser storage.
- Saved routes use compact count/date rows on mobile. Swipe or the actions button
  reveals deletion, which also remains keyboard accessible. New records retain
  their actual creation time; older records do not receive an invented date.
- Event gallery, typography, schedule/price panel, description/actions and related
  cards follow the export. Permanent places without a dated session or period
  display price without an invented schedule. Existing sharing/calendar behavior
  and publication visibility rules remain in use.
- Mobile email login/registration proportions are adjusted; confirmation and form
  errors are retained. Telegram/VK authentication remains excluded.
- Original Figma node `308:1582` supplies the empty-route artwork, bottom glow,
  four navigation vectors, back arrow and plus. The Point cutout still masks both
  the translucent navigation surface and its blur, preserving the transparent gap.

This patch adds `accounts.0003_account_avatar`. User photos use the existing
persistent media volume; deployment must apply the migration before the new code
serves requests (the production entrypoint already runs migrations).

The favorite-heart illustration, exact authentication artwork and profile action
icons still need separate original assets. Reviews, event subscriptions and
delivered notifications require their actual data/behavior and are not simulated.

Validation includes browser route/favorite lifecycles, mobile geometry, native
dialogs, legacy saved records and photo selection; server tests cover upload
authorization, CSRF, image validation/re-encoding and undated place presentation.

## Tablet export, 2 November 2026

Reference: `KidsTime(3).zip`, 22 PNG exports, with tablet artboards at 744px.
The tablet rules apply from 640 through 1023px. Phones retain the mobile layout
below 640px and the desktop layout starts at 1024px.

- Tablet header with search and menu, full-height profile/notifications/settings
  drawers, rounded main surface and a three-column footer. The mobile bottom
  navigation is hidden at tablet widths.
- Main-page active event with its description on the right, fourteen calendar
  dates, two-column collections, wide photo features and the editorial feature.
  Collection size, dates, weather and photographs use the existing catalog data.
  Carousel arrows remain available; tablet playback is manual.
- Initial search guidance and card stack; filtered results use wide text cards.
  Filters open in a right-hand drawer with the existing working date/time controls.
- Event gallery with thumbnails and tools below the main image, a two-column
  schedule/price panel, full-width description, paired actions and two-column
  related cards. Periods and permanent places do not acquire invented sessions.
- Favorites and saved-browser routes use two-column grids with six records per
  page and actual page counts. Resizing restores the appropriate layout without
  dropping records; deletion clamps the current page to the remaining collection.
- Day routes use one wide column, larger point controls and images, paired
  add/map actions and the centered naming dialog. Email login and registration
  use the tablet's centered single-column form.
- The settings drawer edits the same first name, last name and newsletter consent
  as the profile page. Successful saves return to the originating local page;
  external return URLs are rejected. Dialog switching retains the original opener
  for keyboard focus restoration.

The archive contains reference screenshots rather than separate vector/artwork
assets. The menu uses a text control until the original header icon is supplied;
existing authentication artwork and empty-state illustrations are retained.
Reviews, event subscriptions, personal notifications and account-synced routes
still require their actual data and behavior. Telegram/VK login remain excluded.

Validation: browser geometry and route/favorite lifecycles at 320, 402, 639, 640,
744, 834, 1024 and 1440px; focused tablet checks also cover 1023px, drawer focus,
filter keyboard controls, gallery, collection pagination, resize and deletion.
Tests for settings persistence and return-URL validation are included. The full
Django test run still needs CI: the local visual-preview runtime does not have
the application's server dependencies or PostGIS. Compiled CSS is regenerated
from Tailwind. No schema migration is added by this tablet patch.

## Desktop initial search, 3 November 2026

Reference: `KidsTime(4).zip`, `Main wrapper.png` (1440 × 87) and
`Frame 461.png` (1004 × 1736). This change targets the catalog's initial
«Найдите своё событие» state rather than an individual event detail page.

- Desktop initial search shows the guidance, a 372px map action and the existing
  original magnifier illustration. Event cards, pagination and the phone/tablet
  discovery stack appear in their appropriate result/layout states.
- The 300px filter column has separate rounded groups, date inputs, radio choices
  for venue format, a keyboard-operable time range and apply/reset actions. The
  native format select remains available on smaller screens and without JavaScript;
  resizing preserves its value and submits exactly one format field.
- The time handles expose clock values to assistive technology. Untouched handles
  do not introduce time constraints; chosen times are displayed and retained.
- Additional working filters: children's room and cafe/restaurant at a venue,
  and Pushkin Card acceptance for an event. `catalog.0004_catalog_additional_filters`
  adds nullable flags; existing records remain unknown until verified in admin.
  Only explicit true values match. The list and map share the same filter logic.
  Existing imports do not overwrite these editor-maintained flags.
- Accessibility and stroller access remain separate. No sample address, preset
  age restriction, avatar or route count from the reference is inserted as data.

The wordmark, route vector and account avatar use the existing shared header.
The notification control remains textual: the PNG archive has no standalone bell
vector, and the attempt to retrieve the original design assets reached the Figma
MCP Starter-plan limit. No screenshot is embedded as a product background or icon.

Validation covers initial/results/empty search, combined filters, form persistence,
unknown flags, geolocation, time keyboard controls, format changes across widths
and Tailwind output. Browser checks use 320, 402, 744, 834, 1024, 1440 and 1920px;
the full Django suite and migration consistency are checked in CI.

## Desktop 404, 5 November 2026

Reference: Figma node `773:13869` and `KidsTime(5).zip` (`Event page.png`,
`Footer.png`, `Vector 3.png`). The page uses the design's title, caption,
547 × 290 illustration, rounded main surface and desktop footer spacing.
The signpost, mirrored star, notification vector and footer glow are original
assets downloaded from the design context, stored locally with the application.

The existing shared header/footer links and real account state are retained;
unavailable publications, social destinations and sample counters are not added.
The phone layout keeps a home action. Styles are scoped to the 404 body or its
content, leaving the 500 page and other pages unchanged. The standard Django
404 handler continues to return HTTP 404. No migration is required.

Validation: browser checks at 320, 402, 639, 640, 744, 834, 1024, 1440 and 1920px
cover image loading, overflow, search, home navigation, notification keyboard
focus and the separate 500 template. At 1440px the main surface ends at 629px,
the illustration is 547 × 290px and the footer is 395px tall, matching the design.
A server regression test exercises the real unknown-URL handler with DEBUG off.

## Day route, 6 November 2026

The supplied `Route.png` adds travel-time badges between stops and an explicit
origin. The implementation supports browser location, confirmed map selection,
optional address lookup, and walking/driving/transit estimates from Yandex Route
Details. Existing route ordering, browser saves and actual favorite state are kept.
The storage note is separate from the summary card as in the reference.

Travel times require `YANDEX_ROUTER_API_KEY`; address lookup uses the optional
`YANDEX_GEOCODER_API_KEY`. Neither key is exposed in HTML. Missing configuration
or provider failures leave working external links and never substitute sample
minutes or straight-line estimates. The day-route header reuses the original bell
vector and geometry already supplied for the 404 reference.

See `docs/features/day-route.md` for setup, temporary-location handling, limits and
verification. No schema or production Compose change is added.

### Day route follow-up, 6 November 2026

Removed the travel-time badges, fallback time links, total estimate and refresh
controls by product request. Stops retain compact dashed connections. The page no
longer exposes the routing endpoint or requests estimates, even with a configured
router key. Browser geolocation, confirmed map/address selection, reordering,
saving and external Yandex Maps directions remain available. The existing backend
is retained separately; it is not invoked by the day-route page.
