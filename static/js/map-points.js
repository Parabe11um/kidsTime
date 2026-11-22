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
