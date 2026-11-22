import test from "node:test";
import assert from "node:assert/strict";
import { normalizeWalkRefs, personalPointRef, personalPointId, resolveWalkPoints, resolvePersonalOrigin, normalizeSavedWalks } from "../static/js/map-points.js";

const home = { id: "home", name: "Дом", address: "Наш адрес", note: "Подъезд со двора", lat: 55.75, lng: 37.6 };
const park = { id: "park", name: "Площадка", lat: 55.76, lng: 37.61 };
const event = { id: 7, title: "Музей", lat: 55.77, lng: 37.62, age: "6+", date: "25 ноября", url: "/events/museum/" };

test("mixed selections preserve their order and distinguish catalog IDs from personal IDs", () => {
  assert.deepEqual(normalizeWalkRefs([7, "personal:home", "007", "personal:park", "personal:home"]), ["7", "personal:home", "personal:park"]);
  assert.deepEqual(normalizeWalkRefs([0, -1, true, {}, "0", "9223372036854775808", "personal:", "personal:../home", NaN, Infinity]), []);
  assert.equal(normalizeWalkRefs(Array.from({length: 20}, (_, i) => i + 1)).length, 9);
  assert.equal(personalPointRef("7"), "personal:7");
  assert.equal(personalPointId("personal:7"), "7");
  assert.equal(personalPointId("7"), null);
});

test("resolving a mixed route keeps the user's order and does not fabricate personal event facts", () => {
  const result = resolveWalkPoints(["personal:park", "7", "personal:home"], [event], [home, park]);
  assert.deepEqual(result.map(point => point.title), ["Площадка", "Музей", "Дом"]);
  assert.deepEqual(result.map(point => point.kind), ["personal", "event", "personal"]);
  assert.equal(result[0].date, ""); assert.equal(result[0].age, ""); assert.equal(result[0].url, "");
  assert.equal(result[1].url, "/events/museum/");
  assert.equal(result[2].description, "Подъезд со двора");
});

test("personal-only routes work without catalog data; edited and deleted library points are resolved live", () => {
  assert.equal(resolveWalkPoints(["personal:home"], [], [home])[0].lat, 55.75);
  assert.equal(resolveWalkPoints(["personal:home"], [], [{...home, lat: 56}])[0].lat, 56);
  assert.deepEqual(resolveWalkPoints(["personal:home"], [], []), []);
  assert.deepEqual(resolveWalkPoints(["personal:home"], [], [{...home, lat: null}]), []);
});

test("origin is resolved only from an explicitly saved personal reference", () => {
  assert.deepEqual(resolvePersonalOrigin("personal:home", [home]), {lat: 55.75, lng: 37.6, label: "Дом", source: "personal", pointId: "home"});
  assert.equal(resolvePersonalOrigin("personal:missing", [home]), null);
  assert.equal(resolvePersonalOrigin("7", [home]), null);
  assert.equal(resolvePersonalOrigin("personal:home", [{...home, lng: Infinity}]), null);
});

test("old saved routes keep their IDs, names and dates; new routes keep mixed stops and personal origin", () => {
  const date = "2026-11-23T12:00:00.000Z";
  const routes = normalizeSavedWalks([
    {id: "old", name: "  Старый маршрут  ", ids: [7, 9], created_at: date},
    {id: "new", name: "Новый маршрут", ids: ["7", "personal:park"], origin_id: "personal:home", origin: {lat: 55, lng: 37, source: "geolocation"}},
  ]);
  assert.deepEqual(routes[0], {id: "old", name: "Старый маршрут", ids: ["7", "9"], created_at: date});
  assert.deepEqual(routes[1], {id: "new", name: "Новый маршрут", ids: ["7", "personal:park"], origin_id: "personal:home"});
  assert.equal(JSON.stringify(routes).includes('geolocation'), false);
});

test("damaged route records, duplicated IDs and raw geolocation origins are not restored", () => {
  const routes = normalizeSavedWalks([null, {id:"bad/path", name:"bad", ids:[7]}, {id:"ok",name:"Семья",ids:[7],origin_id:"55,37"},
    {id:"ok",name:"Дубль",ids:[9]}, {id:"empty",name:"",ids:[7]}, {id:"none",name:"Нет мест",ids:[]}]);
  assert.deepEqual(routes, [{id:"ok",name:"Семья",ids:["7"]}]);
});
