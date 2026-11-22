const root = document.querySelector("[data-map-root]");

if (root) {
  // Django fingerprints the module URL in the template, including after collectstatic.
  const { createMapPointStore, MAP_POINTS_KEY, MAP_POINTS_LIMIT, parseCoordinate, validCoordinates } = await import(root.dataset.pointsModule);
  const store = createMapPointStore({
    getItem: key => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
  });
  const find = selector => root.querySelector(selector);
  const unavailable = find("[data-map-unavailable]");
  const eventSheet = find("[data-map-sheet]");
  const personalSheet = find("[data-personal-sheet]");
  const panel = find("[data-points-panel]");
  const panelButton = find("[data-points-open]");
  const dialog = find("[data-point-dialog]");
  const form = find("[data-point-form]");
  const selection = find("[data-point-selection]");
  const errorText = find("[data-point-error]");
  const status = find("[data-points-status]");
  const pointText = point => `${point.lat.toFixed(6)}, ${point.lng.toFixed(6)}`;
  let map, api, draftMarker, draft = null, selecting = false, activeId = null, opener;
  let points = [], personalMarkers = [], eventMarkers = [], catalogLoading = false;

  function announce(message) { status.textContent = message; status.hidden = !message; }
  function messageFor(error) {
    return ({
      name: "Укажите название точки: от 1 до 80 символов.",
      address: "Адрес должен быть не длиннее 200 символов.",
      note: "Заметка должна быть не длиннее 500 символов.",
      coordinates: "Укажите широту от −90 до 90 и долготу от −180 до 180. Например: 55.7558 и 37.6176.",
      limit: `Можно сохранить не более ${MAP_POINTS_LIMIT} точек. Удалите ненужную точку и попробуйте снова.`,
      not_found: "Эта точка уже удалена в другой вкладке. Закройте редактор и выберите другую точку.",
      storage: "Не удалось сохранить изменения. Проверьте, разрешено ли браузеру хранить данные сайта, и попробуйте снова.",
    })[error.code] || "Не удалось сохранить точку. Попробуйте ещё раз.";
  }
  function restoreFocus() {
    (opener?.isConnected && opener.getClientRects().length ? opener : panelButton).focus({ preventScroll: true });
  }
  function closeSheets() {
    eventSheet.hidden = true; personalSheet.hidden = true; panel.hidden = true;
    panelButton.setAttribute("aria-expanded", "false"); activeId = null;
  }
  function setSelecting(value) {
    selecting = value; selection.hidden = !value;
    root.classList.toggle("is-selecting-point", value);
    find("[data-point-add]").setAttribute("aria-pressed", String(value));
  }
  function clearDraft() {
    setSelecting(false); draft = null;
    if (draftMarker) { map.removeChild(draftMarker); draftMarker = null; }
  }
  function paintDraft() {
    if (draftMarker) { map.removeChild(draftMarker); draftMarker = null; }
    if (!map || !validCoordinates(draft)) return;
    const pin = document.createElement("div");
    pin.className = "map-marker map-marker--draft"; pin.setAttribute("aria-hidden", "true");
    pin.append(document.createElement("span"));
    draftMarker = new api.YMapMarker({ coordinates: [draft.lng, draft.lat], zIndex: 1000 }, pin);
    map.addChild(draftMarker);
  }
  function centerOn(point) {
    map?.update({ location: { center: [point.lng, point.lat], zoom: 16 } });
  }
  function renderPersonalMarkers() {
    if (!map) return;
    personalMarkers.forEach(marker => map.removeChild(marker)); personalMarkers = [];
    points.forEach(point => {
      const button = document.createElement("button");
      button.type = "button"; button.className = "map-marker map-marker--personal";
      button.setAttribute("aria-label", `Моя точка: ${point.name}`);
      button.append(document.createElement("span"));
      button.addEventListener("click", event => { event.stopPropagation(); if (!selecting) showPoint(point.id, button); });
      const marker = new api.YMapMarker({ coordinates: [point.lng, point.lat], zIndex: 200 }, button);
      map.addChild(marker); personalMarkers.push(marker);
    });
  }
  function refreshPoints() {
    try { points = store.list(); }
    catch (_) {
      announce("Браузер не разрешает открыть сохранённые точки. Проверьте настройки хранения данных сайта.");
      return false;
    }
    find("[data-points-count]").textContent = String(points.length);
    find("[data-points-empty]").hidden = Boolean(points.length);
    const list = find("[data-points-list]"); list.replaceChildren();
    points.forEach(point => {
      const item = document.createElement("li"), button = document.createElement("button");
      button.type = "button";
      const name = document.createElement("strong"), address = document.createElement("span");
      name.textContent = point.name; address.textContent = point.address || pointText(point);
      button.append(name, address); item.append(button); list.append(item);
      button.addEventListener("click", () => showPoint(point.id, panelButton));
    });
    renderPersonalMarkers();
    if (activeId) {
      if (points.some(point => point.id === activeId)) showPoint(activeId, opener, false);
      else { personalSheet.hidden = true; activeId = null; panelButton.focus(); announce("Точка удалена в другой вкладке."); }
    }
    return true;
  }
  function showPoint(id, button, focus = true) {
    const point = points.find(item => item.id === id);
    if (!point) return;
    closeSheets(); activeId = id; opener = button;
    find("[data-personal-title]").textContent = point.name;
    const address = find("[data-personal-address]"); address.textContent = point.address; address.hidden = !point.address;
    find("[data-personal-coordinates]").textContent = pointText(point);
    const note = find("[data-personal-note]"); note.textContent = point.note; note.hidden = !point.note;
    find("[data-personal-route]").href = `https://yandex.ru/maps/?rtext=~${encodeURIComponent(`${point.lat},${point.lng}`)}&rtt=pd`;
    personalSheet.hidden = false;
    if (focus) { centerOn(point); find("[data-personal-close]").focus({ preventScroll: true }); }
  }
  function readForm() {
    const value = name => form.elements.namedItem(name).value;
    return { id: draft?.id ?? null, name: value("name"), address: value("address"), note: value("note"),
      lat: parseCoordinate(value("lat")), lng: parseCoordinate(value("lng")) };
  }
  function openEditor() {
    setSelecting(false); announce("");
    find("[data-point-editor-title]").textContent = draft.id ? "Изменить точку" : "Новая точка";
    for (const name of ["name", "address", "note"]) form.elements.namedItem(name).value = draft[name];
    for (const name of ["lat", "lng"]) form.elements.namedItem(name).value = Number.isFinite(draft[name]) ? draft[name].toFixed(6) : "";
    errorText.hidden = true;
    find("[data-point-pick]").hidden = !map;
    dialog.returnValue = ""; dialog.showModal();
    form.elements.namedItem("name").focus(); paintDraft();
  }
  function beginSelection() {
    setSelecting(true); selection.querySelector("button").focus({ preventScroll: true });
    announce("");
  }
  function beginAdd(button) {
    opener = button; closeSheets(); clearDraft();
    draft = { id: null, name: "", address: "", note: "", lat: NaN, lng: NaN };
    if (map) beginSelection(); else openEditor();
  }
  function cancelDraft() {
    const id = draft?.id; clearDraft(); announce("");
    if (id && points.some(point => point.id === id)) showPoint(id, panelButton);
    else restoreFocus();
  }
  root.querySelectorAll("[data-point-add]").forEach(button => button.addEventListener("click", () => beginAdd(button)));
  find("[data-point-manual]").addEventListener("click", openEditor);
  find("[data-point-selection-cancel]").addEventListener("click", cancelDraft);
  find("[data-point-pick]").addEventListener("click", () => {
    draft = readForm(); dialog.close("pick"); beginSelection();
  });
  root.querySelectorAll("[data-point-cancel]").forEach(button => button.addEventListener("click", () => dialog.close("cancel")));
  dialog.addEventListener("close", () => {
    if (dialog.returnValue === "pick") return;
    if (dialog.returnValue !== "saved") cancelDraft();
  });
  form.addEventListener("submit", event => {
    event.preventDefault();
    try {
      const values = readForm(), point = store.save(values, values.id);
      dialog.close("saved"); clearDraft(); refreshPoints(); showPoint(point.id, panelButton);
      announce(values.id ? "Изменения сохранены в этом браузере." : "Точка сохранена в этом браузере.");
    } catch (error) {
      errorText.textContent = messageFor(error); errorText.hidden = false;
      const field = error.code === "coordinates" ? "lat" : error.code;
      form.elements.namedItem(field)?.focus();
    }
  });
  panelButton.addEventListener("click", () => {
    const open = panel.hidden; clearDraft(); closeSheets(); announce("");
    if (open) { refreshPoints(); panel.hidden = false; panelButton.setAttribute("aria-expanded", "true"); find("[data-points-close]").focus(); }
  });
  find("[data-points-close]").addEventListener("click", () => { closeSheets(); panelButton.focus(); });
  find("[data-personal-close]").addEventListener("click", () => { closeSheets(); restoreFocus(); });
  find("[data-personal-edit]").addEventListener("click", () => {
    const point = points.find(item => item.id === activeId); if (!point) return;
    draft = { ...point }; closeSheets(); opener = panelButton; openEditor();
  });
  find("[data-personal-delete]").addEventListener("click", () => {
    const point = points.find(item => item.id === activeId);
    if (!point || !window.confirm(`Удалить точку «${point.name}» из этого браузера?`)) return;
    try {
      store.remove(point.id); closeSheets(); refreshPoints(); panelButton.focus(); announce("Точка удалена.");
    } catch (error) { announce(messageFor(error)); }
  });
  document.addEventListener("keydown", event => {
    if (event.key !== "Escape" || dialog.open) return;
    if (selecting) { event.preventDefault(); cancelDraft(); }
    else if (!panel.hidden || !personalSheet.hidden) { closeSheets(); restoreFocus(); }
  });
  window.addEventListener("storage", event => {
    if (event.key === MAP_POINTS_KEY || event.key === null) refreshPoints();
  });
  find("[data-map-sheet-close]").addEventListener("click", () => { eventSheet.hidden = true; });
  find("[data-personal-tools]").hidden = false;
  refreshPoints();

  function showEvent(event) {
    if (selecting) return;
    closeSheets(); announce("");
    const image = find("[data-map-sheet-image]");
    image.hidden = !event.cover;
    if (event.cover) image.src = event.cover; else image.removeAttribute("src");
    find("[data-map-sheet-category]").textContent = event.category;
    find("[data-map-sheet-title]").textContent = event.title;
    find("[data-map-sheet-address]").textContent = event.address;
    find("[data-map-sheet-age]").textContent = event.age;
    find("[data-map-sheet-price]").textContent = event.price;
    find("[data-map-sheet-link]").href = event.url;
    find("[data-map-sheet-route]").href = `https://yandex.ru/maps/?rtext=~${encodeURIComponent(`${event.lat},${event.lng}`)}&rtt=pd`;
    const walkButton = find("[data-map-sheet-walk]");
    walkButton.dataset.walkButton = String(event.id);
    window.KidsTimeWalk?.refreshButton(walkButton);
    eventSheet.hidden = false;
  }
  async function loadEvents() {
    if (catalogLoading || !map) return;
    catalogLoading = true;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 12000);
    const retry = find("[data-map-events-retry]"); retry.disabled = true;
    try {
      const response = await fetch(root.dataset.endpoint, { headers: { Accept: "application/json" }, signal: controller.signal });
      if (!response.ok) throw new Error("events unavailable");
      const payload = await response.json();
      if (!Array.isArray(payload.results)) throw new Error("events unavailable");
      eventMarkers.forEach(marker => map.removeChild(marker)); eventMarkers = [];
      payload.results.filter(validCoordinates).forEach(event => {
        const button = document.createElement("button");
        button.type = "button"; button.className = "map-marker"; button.setAttribute("aria-label", event.title);
        button.append(document.createElement("span"));
        button.addEventListener("click", click => { click.stopPropagation(); showEvent(event); });
        const marker = new api.YMapMarker({ coordinates: [event.lng, event.lat] }, button);
        map.addChild(marker); eventMarkers.push(marker);
      });
      find("[data-map-events-status]").hidden = true;
    } catch (_) { find("[data-map-events-status]").hidden = false; }
    finally { clearTimeout(timer); catalogLoading = false; retry.disabled = false; }
  }
  find("[data-map-events-retry]").addEventListener("click", loadEvents);

  async function loadMap() {
    if (root.dataset.mapEnabled !== "true") { unavailable.hidden = false; return; }
    const script = document.querySelector("[data-map-api]");
    let timer, onLoad, onError;
    try {
      const ready = window.ymaps3 ? window.ymaps3.ready : new Promise((resolve, reject) => {
        if (!script) { reject(new Error("map unavailable")); return; }
        onLoad = () => window.ymaps3 ? Promise.resolve(window.ymaps3.ready).then(resolve, reject) : reject(new Error("map unavailable"));
        onError = () => reject(new Error("map unavailable"));
        script.addEventListener("load", onLoad, { once: true });
        script.addEventListener("error", onError, { once: true });
      });
      await Promise.race([ready, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("map timeout")), 10000); })]);
      api = window.ymaps3;
      const center = { lat: Number(root.dataset.centerLat), lng: Number(root.dataset.centerLng) };
      const hasCenter = root.dataset.centerLat && validCoordinates(center);
      map = new api.YMap(find("#events-map"), {
        location: { center: hasCenter ? [center.lng, center.lat] : [37.6176, 55.7558], zoom: hasCenter ? 12 : 10 },
        behaviors: ["drag", "scrollZoom", "pinchZoom", "dblClick"],
      });
      map.addChild(new api.YMapDefaultSchemeLayer({}));
      map.addChild(new api.YMapDefaultFeaturesLayer({}));
      map.addChild(new api.YMapListener({ layer: "any", onClick: (object, event) => {
        if (!selecting || object?.type === "marker") return;
        const point = { lng: event.coordinates[0], lat: event.coordinates[1] };
        if (validCoordinates(point)) { Object.assign(draft, point); openEditor(); }
      } }));
      unavailable.hidden = true; renderPersonalMarkers(); paintDraft();
      if (dialog.open) find("[data-point-pick]").hidden = false;
      loadEvents();
    } catch (_) { unavailable.hidden = false; }
    finally {
      clearTimeout(timer);
      if (onLoad) script.removeEventListener("load", onLoad);
      if (onError) script.removeEventListener("error", onError);
    }
  }
  loadMap();
}
