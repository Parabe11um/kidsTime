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
