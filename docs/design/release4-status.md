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

Reference: `KidsTime(2).zip`, 29 native PNG exports. The mobile overrides apply
below 768px; the desktop search, gallery, authentication and sidebar layouts stay
in place.

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
