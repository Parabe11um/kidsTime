export const MAP_POINTS_KEY = "kidstime:map-points:v1";
export const MAP_POINTS_LIMIT = 50;

export class MapPointError extends Error {
  constructor(code) { super(code); this.code = code; }
}

export function parseCoordinate(value) {
  if (typeof value !== "string" || !/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(value.trim())) return NaN;
  return Number(value.trim().replace(",", "."));
}

export function validCoordinates(point) {
  return point && typeof point.lat === "number" && typeof point.lng === "number" &&
    Number.isFinite(point.lat) && Number.isFinite(point.lng) && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180;
}

function fields(value) {
  if (!value || typeof value !== "object" || !validCoordinates(value)) throw new MapPointError("coordinates");
  const name = typeof value.name === "string" ? value.name.trim() : "";
  if (!name || name.length > 80 || /[\u0000-\u001f\u007f]/.test(name)) throw new MapPointError("name");
  const address = value.address === undefined ? "" : value.address;
  const note = value.note === undefined ? "" : value.note;
  if (typeof address !== "string" || address.trim().length > 200) throw new MapPointError("address");
  if (typeof note !== "string" || note.trim().length > 500) throw new MapPointError("note");
  return { name, address: address.trim(), note: note.trim(), lat: value.lat, lng: value.lng };
}

const validId = id => typeof id === "string" && /^[\w-]{1,80}$/.test(id);

// Only explicitly saved, user-entered points belong here. Catalog/Yandex data and
// the device's current location are never copied into this store automatically.
export function createMapPointStore(storage, idFactory = () => `point-${crypto.randomUUID()}`) {
  function list() {
    let raw;
    try { raw = storage.getItem(MAP_POINTS_KEY); }
    catch (_) { throw new MapPointError("storage"); }
    if (!raw || raw.length > 100000) return [];
    let records;
    try { records = JSON.parse(raw); } catch (_) { return []; }
    if (!Array.isArray(records)) return [];
    const points = [], ids = new Set();
    for (const record of records) {
      if (points.length === MAP_POINTS_LIMIT) break;
      if (!record || !validId(record.id) || ids.has(record.id)) continue;
      try {
        points.push({ id: record.id, ...fields(record) });
        ids.add(record.id);
      } catch (_) { /* Ignore malformed records without breaking the map. */ }
    }
    return points;
  }

  function write(points) {
    try { storage.setItem(MAP_POINTS_KEY, JSON.stringify(points)); }
    catch (_) { throw new MapPointError("storage"); }
  }

  function save(value, id = null) {
    const point = fields(value), points = list();
    if (id !== null) {
      const index = points.findIndex(item => item.id === id);
      if (index === -1) throw new MapPointError("not_found");
      points[index] = { id, ...point };
    } else {
      if (points.length >= MAP_POINTS_LIMIT) throw new MapPointError("limit");
      id = idFactory();
      if (!validId(id) || points.some(item => item.id === id)) throw new MapPointError("id");
      points.push({ id, ...point });
    }
    write(points);
    return { id, ...point };
  }

  function remove(id) {
    const points = list();
    if (!points.some(point => point.id === id)) throw new MapPointError("not_found");
    write(points.filter(point => point.id !== id));
  }

  return { list, save, remove };
}

// Namespaced references cannot collide with catalog event IDs. Old numeric
// selections and saved routes remain readable without a data migration.
export function personalPointRef(id) { return validId(id) ? `personal:${id}` : null; }
export function personalPointId(ref) {
  return typeof ref === "string" && ref.startsWith("personal:") && validId(ref.slice(9)) ? ref.slice(9) : null;
}

export function normalizeWalkRefs(values, limit = 9) {
  const refs = [];
  for (const value of Array.isArray(values) ? values : []) {
    let ref = typeof value === "string" ? value.trim() : typeof value === "number" && Number.isSafeInteger(value) ? String(value) : "";
    if (!personalPointId(ref)) {
      if (!/^[0-9]{1,19}$/.test(ref) || BigInt(ref) < 1n || BigInt(ref) > 9223372036854775807n) continue;
      ref = String(BigInt(ref));
    }
    if (!refs.includes(ref)) refs.push(ref);
    if (refs.length === limit) break;
  }
  return refs;
}

export function resolveWalkPoints(refs, events, personalPoints) {
  const catalog = new Map((Array.isArray(events) ? events : []).filter(validCoordinates).map(event => [String(event.id), event]));
  const personal = new Map((Array.isArray(personalPoints) ? personalPoints : []).map(point => [point.id, point]));
  return normalizeWalkRefs(refs).flatMap(ref => {
    const pointId = personalPointId(ref);
    if (!pointId) {
      const event = catalog.get(ref);
      return event ? [{ ...event, id: ref, kind: "event" }] : [];
    }
    const point = personal.get(pointId);
    if (!point) return [];
    try {
      const place = fields(point);
      return [{ id: ref, pointId, kind: "personal", title: place.name, venue: "Моя точка", address: place.address || `${place.lat.toFixed(6)}, ${place.lng.toFixed(6)}`,
        description: place.note, lat: place.lat, lng: place.lng, url: "", cover: "", date: "", age: "", price: "" }];
    } catch (_) { return []; }
  });
}

export function resolvePersonalOrigin(ref, personalPoints) {
  const id = personalPointId(ref);
  const point = id && personalPoints.find(point => point.id === id);
  if (!point) return null;
  try {
    const place = fields(point);
    return { lat: place.lat, lng: place.lng, label: place.name, source: "personal", pointId: id };
  } catch (_) { return null; }
}

export function normalizeSavedWalks(values) {
  if (!Array.isArray(values)) return [];
  const routes = [], unique = new Set();
  for (const value of values) {
    if (routes.length === 20) break;
    if (!value || !validId(value.id) || unique.has(value.id) || typeof value.name !== "string" || !value.name.trim()) continue;
    const ids = normalizeWalkRefs(value.ids);
    if (!ids.length) continue;
    const route = { id: value.id, name: value.name.trim().slice(0, 80), ids };
    if (personalPointId(value.origin_id)) route.origin_id = value.origin_id;
    if (typeof value.created_at === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value.created_at) && Number.isFinite(Date.parse(value.created_at))) route.created_at = value.created_at;
    routes.push(route); unique.add(route.id);
  }
  return routes;
}
