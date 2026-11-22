import test from "node:test";
import assert from "node:assert/strict";
import { createMapPointStore, MAP_POINTS_KEY, MAP_POINTS_LIMIT, parseCoordinate } from "../static/js/map-points.js";

const place = { name: "  Наша площадка  ", address: "Москва, наш двор", note: "Есть качели", lat: 55.75, lng: 37.62 };
function memory() {
  const values = new Map();
  return { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key, value) };
}
function expectCode(callback, code) { assert.throws(callback, error => error.code === code); }

test("personal points survive reopening; edit keeps identity; delete preserves other browser data", () => {
  const storage = memory();
  storage.setItem("kidstime:favorites", "[7]");
  storage.setItem("kidstime:saved-walks", '[{"id":"route-1"}]');
  const store = createMapPointStore(storage, () => "my-point");
  const saved = store.save(place);
  assert.equal(saved.name, "Наша площадка");
  const reopened = createMapPointStore(storage, () => "second");
  assert.deepEqual(reopened.list(), [saved]);
  const edited = reopened.save({ ...place, name: "Дом", lat: 55.76 }, saved.id);
  assert.equal(edited.id, saved.id);
  assert.equal(store.list().length, 1);
  assert.equal(store.list()[0].lat, 55.76);
  reopened.save({ ...place, name: "Кафе" });
  store.remove(saved.id);
  assert.equal(reopened.list()[0].name, "Кафе");
  assert.equal(storage.getItem("kidstime:favorites"), "[7]");
  assert.equal(storage.getItem("kidstime:saved-walks"), '[{"id":"route-1"}]');
});

test("invalid input never replaces a saved record; zero coordinates are accepted", () => {
  const storage = memory(), store = createMapPointStore(storage, () => "valid");
  const saved = store.save(place);
  for (const value of [NaN, Infinity, -Infinity, "55", true, null, 91, -91]) {
    expectCode(() => store.save({ ...place, lat: value }, saved.id), "coordinates");
  }
  for (const value of [181, -181, undefined]) expectCode(() => store.save({ ...place, lng: value }), "coordinates");
  for (const name of ["", "  ", "a".repeat(81), "bad\nname", 123]) expectCode(() => store.save({ ...place, name }), "name");
  expectCode(() => store.save({ ...place, address: "a".repeat(201) }), "address");
  expectCode(() => store.save({ ...place, note: "a".repeat(501) }), "note");
  assert.deepEqual(store.list(), [saved]);
  assert.equal(store.save({ ...place, lat: 0, lng: 0 }, saved.id).lat, 0);
  for (const [lat, lng] of [[90, 180], [-90, -180]]) assert.equal(store.save({ ...place, lat, lng }, saved.id).lat, lat);
});

test("coordinate entry accepts Russian decimal commas and rejects empty or non-decimal input", () => {
  assert.equal(parseCoordinate(" 55,7558 "), 55.7558);
  assert.equal(parseCoordinate("-37.62"), -37.62);
  assert.equal(parseCoordinate("0"), 0);
  for (const value of ["", " ", "NaN", "Infinity", "0x10", "1e2", "55,7,8", true, null, "55.7 Moscow"]) {
    assert.ok(Number.isNaN(parseCoordinate(value)), String(value));
  }
});

test("bad JSON, untrusted fields, duplicate IDs and damaged records do not break reading", () => {
  const storage = memory(), store = createMapPointStore(storage);
  for (const raw of ["{broken", "null", "{}", "42", '"text"']) {
    storage.setItem(MAP_POINTS_KEY, raw);
    assert.deepEqual(store.list(), []);
  }
  storage.setItem(MAP_POINTS_KEY, JSON.stringify([
    null, { id: "../invalid", ...place }, { id: "bad", ...place, lat: null },
    { id: "good", ...place, html: "<script>" }, { id: "good", ...place },
  ]));
  assert.deepEqual(store.list(), [{ id: "good", ...place, name: "Наша площадка" }]);
});

test("a full store permits editing and rejects new records without losing existing points", () => {
  const storage = memory(); let id = 0;
  const store = createMapPointStore(storage, () => `point-${++id}`);
  for (let i = 0; i < MAP_POINTS_LIMIT; i++) store.save({ ...place, name: `Место ${i}` });
  const before = storage.getItem(MAP_POINTS_KEY);
  expectCode(() => store.save(place), "limit");
  assert.equal(storage.getItem(MAP_POINTS_KEY), before);
  store.save({ ...place, name: "Обновлённое место" }, "point-1");
  assert.equal(store.list().length, MAP_POINTS_LIMIT);
  store.remove("point-1");
  store.save(place);
  assert.equal(store.list().length, MAP_POINTS_LIMIT);
});

test("storage/quota failures are reported and never look like successful edits or deletion", () => {
  const storage = memory(), store = createMapPointStore(storage, () => "saved");
  const saved = store.save(place);
  const fail = () => { throw new Error("blocked"); };
  const readBlocked = createMapPointStore({ getItem: fail, setItem: fail });
  expectCode(() => readBlocked.list(), "storage");
  expectCode(() => readBlocked.save(place), "storage");
  const quotaBlocked = createMapPointStore({ getItem: storage.getItem, setItem: fail });
  expectCode(() => quotaBlocked.save({ ...place, name: "Changed" }, saved.id), "storage");
  expectCode(() => quotaBlocked.remove(saved.id), "storage");
  assert.deepEqual(store.list(), [saved]);
});

test("another tab's additions are preserved; a removed point cannot be silently recreated by an old edit", () => {
  const storage = memory();
  const tabA = createMapPointStore(storage, () => "a"), tabB = createMapPointStore(storage, () => "b");
  tabA.save(place); tabB.save({ ...place, name: "Вторая точка" });
  tabA.save({ ...place, note: "Правка" }, "a");
  assert.deepEqual(tabA.list().map(point => point.id), ["a", "b"]);
  tabB.remove("a");
  expectCode(() => tabA.save(place, "a"), "not_found");
  expectCode(() => tabA.remove("a"), "not_found");
  assert.equal(tabB.list().length, 1);
});

test("an ID collision cannot overwrite a different place", () => {
  const store = createMapPointStore(memory(), () => "same-id");
  store.save(place);
  expectCode(() => store.save({ ...place, name: "Другая точка" }), "id");
  assert.equal(store.list()[0].name, "Наша площадка");
});
