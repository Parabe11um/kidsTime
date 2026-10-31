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

- Separate exports of the empty-search magnifier, favorites heart, empty-route
  map, authentication artwork and profile icons. Full-screen PNGs are references,
  not assets to embed in the application. Add the original assets to their design
  slots when the individual exports are supplied.
- Profile header, photo upload, real collection counters and account settings.
- Account-owned saved routes, route list, name sheet and editing/deletion states.
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

Still requires original source assets: the empty-route map, favorites heart,
error-page illustrations, auth background and header/drawer icon set. These are
flattened inside the supplied full-screen PNGs. After one successful asset fetch,
Figma MCP returned its Starter-plan request limit. The existing auth gradient is
retained; notifications currently use a text control in the header. Reference
screenshots are not embedded as page backgrounds or cropped into fake UI assets.

The exported settings/review/subscription screens also refer to functionality
not in the current data model: event-update subscriptions, delivered personal
notifications, review/rating records and profile photo uploads. No mock review
counts, sample notifications, non-working social buttons or fake subscriptions
are introduced. Telegram/VK login remain excluded; email confirmation is retained.

Validation: browser interaction and overflow checks on 1440, 1024, 834, 402 and
320px; route lifecycle, final favorite removal, dialogs and local-storage errors;
Django filter/pagination/settings tests run in CI. No schema migration is added.
