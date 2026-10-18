# Demo photographs

These are unchanged local copies of the six photographs already referenced by
`seed_demo`. They are illustrative demo content, not verified photographs of the
venues or events. Real catalogue entries should use organizer-provided or owned
images with their source and rights recorded in `EventImage`.

Downloaded on 2026-10-18 using the existing image parameters:
`?auto=format&fit=crop&w=1200&q=80`.

| Local file | Original source |
| --- | --- |
| `static/images/demo/space.jpg` | https://images.unsplash.com/photo-1446776811953-b23d57bd21aa |
| `static/images/demo/nature.jpg` | https://images.unsplash.com/photo-1500530855697-b586d89ba3ee |
| `static/images/demo/fox.jpg` | https://images.unsplash.com/photo-1474511320723-9a56873867b5 |
| `static/images/demo/science.jpg` | https://images.unsplash.com/photo-1532094349884-543bc11b234d |
| `static/images/demo/family.jpg` | https://images.unsplash.com/photo-1503454537195-1dcabb73ffb9 |
| `static/images/demo/park.jpg` | https://images.unsplash.com/photo-1542810634-71277d95dcbb |

`resolve_demo_cover_url` recognizes only these six legacy Unsplash paths and
returns their manifest-backed static URLs. Existing database values are retained,
uploaded covers take priority, and unrelated image URLs pass through unchanged.
Both catalogue cards and detail galleries use the resolved cover URL.
