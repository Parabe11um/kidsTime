(async () => {
  await window.KidsTimeReady;
  const root = document.querySelector("[data-walk-root]");
  const walk = window.KidsTimeWalk;
  if (!root || !walk) return;
  const dialog = root.querySelector("[data-walk-origin-dialog]");
  const confirm = root.querySelector("[data-origin-confirm]");
  const selection = root.querySelector("[data-origin-selection]");
  const dialogStatus = root.querySelector("[data-origin-dialog-status]");
  const originStatus = root.querySelector("[data-walk-origin-status]");
  const randomButton = root.querySelector("[data-walk-random]");
  const randomStatus = root.querySelector("[data-walk-random-status]");
  const geocoder = root.dataset.geocoderEnabled === "true";
  const csrf = root.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  const validPoint = p => p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180;
  const samePoint = (a, b) => validPoint(a) && validPoint(b) && a.lat === b.lat && a.lng === b.lng;
  const pointText = p => `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}`;
  async function post(endpoint, payload, signal) {
    const controller = new AbortController();
    const abort = () => controller.abort();
    if (signal?.aborted) abort(); else signal?.addEventListener("abort", abort, { once: true });
    const timer = setTimeout(abort, 12000);
    try {
      const response = await fetch(endpoint, {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrf, Accept: "application/json" },
        body: JSON.stringify(payload), signal: controller.signal,
      });
      if (!response.ok) throw Object.assign(new Error("request unavailable"), { status: response.status });
      return await response.json();
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener("abort", abort);
    }
  }

  let candidate = null;
  let map, marker, apiPromise, mapPromise, opener;
  let originRevision = 0, geoRevision = 0, searchRevision = 0;
  let randomRequest;

  function randomMessage(text) {
    randomStatus.textContent = text;
    randomStatus.hidden = !text;
  }

  async function generateWalk() {
    const origin = walk.getOrigin();
    if (!origin) {
      openOrigin(randomButton);
      return;
    }
    if (randomRequest) return;

    const request = new AbortController();
    randomRequest = request;
    randomButton.disabled = true;
    randomMessage("Подбираем места рядом с начальной точкой…");
    try {
      const data = await post(root.dataset.randomEndpoint, { origin: { lat: origin.lat, lng: origin.lng } }, request.signal);
      if (request.signal.aborted || root.classList.contains("is-saved")) {
        randomMessage("");
        return;
      }
      if (!Array.isArray(data.ids)) throw new Error("walk unavailable");
      if (!data.ids.length) {
        randomMessage("Поблизости пока нет подходящих мест. Выберите другую начальную точку.");
        return;
      }
      randomRequest = null;
      walk.replaceIds(data.ids);
      randomMessage("");
      walk.notice("Случайный маршрут готов");
    } catch (error) {
      if (request.signal.aborted) return;
      randomMessage(error.status === 429 ? "Слишком много попыток. Попробуйте позже." : "Не удалось подобрать маршрут. Попробуйте ещё раз.");
    } finally {
      randomRequest = null;
      randomButton.disabled = false;
    }
  }
  function paintOrigin() {
    const point = walk.getOrigin();
    const missing = Boolean(walk.getOriginRef() && !point);
    root.querySelector("[data-walk-origin-title]").textContent = point?.source === "geolocation" ? "Ваше текущее местоположение" : "Начальная точка";
    root.querySelector("[data-walk-origin-label]").textContent = point ? (point.label || pointText(point)) : missing ? "Личная точка удалена — выбрать другую" : "Выбрать на карте";
    root.querySelector("[data-origin-clear]").hidden = !point && !missing;
    if (missing) { originMessage("Начальная точка недоступна. Выберите другую или уберите начало маршрута."); originStatus.dataset.missingPoint = "true"; }
    else if (originStatus.dataset.missingPoint) { originMessage(""); delete originStatus.dataset.missingPoint; }
  }
  function originMessage(text) {
    originStatus.textContent = text; originStatus.hidden = !text;
    if (dialog.open) dialogStatus.textContent = text;
  }
  function paintCandidate(recenter = false) {
    confirm.disabled = !validPoint(candidate);
    selection.textContent = candidate ? (candidate.label || `Выбрана точка: ${pointText(candidate)}`) : "Точка пока не выбрана.";
    const form = root.querySelector("[data-origin-coordinate-form]");
    form.elements.lat.value = candidate ? candidate.lat.toFixed(6) : "";
    form.elements.lng.value = candidate ? candidate.lng.toFixed(6) : "";
    if (!map) return;
    if (marker) { map.removeChild(marker); marker = null; }
    if (candidate) {
      const pin = document.createElement("div"); pin.className = "walk-origin-pin"; pin.setAttribute("aria-hidden", "true");
      const number = document.createElement("span"); number.textContent = "1"; pin.append(number);
      marker = new window.ymaps3.YMapMarker({
        coordinates: [candidate.lng, candidate.lat], draggable: true,
        onDragEnd: coords => {
          const point = { lng: coords[0], lat: coords[1], source: "map" };
          if (validPoint(point)) { candidate = point; paintCandidate(); }
        },
      }, pin);
      map.addChild(marker);
      if (recenter) map.update({ location: { center: [candidate.lng, candidate.lat], zoom: 16 } });
    }
  }
  function loadApi() {
    if (apiPromise) return apiPromise;
    apiPromise = new Promise((resolve, reject) => {
      if (!root.dataset.mapKey) { reject(new Error("map unavailable")); return; }
      const timer = setTimeout(() => reject(new Error("map timeout")), 10000);
      const ready = () => {
        if (!window.ymaps3) { clearTimeout(timer); reject(new Error("map unavailable")); return; }
        window.ymaps3.ready.then(() => { clearTimeout(timer); resolve(window.ymaps3); }, () => { clearTimeout(timer); reject(new Error("map unavailable")); });
      };
      if (window.ymaps3) { ready(); return; }
      const script = document.createElement("script"); script.async = true;
      script.src = `https://api-maps.yandex.ru/v3/?apikey=${encodeURIComponent(root.dataset.mapKey)}&lang=ru_RU`;
      script.onload = ready;
      script.onerror = () => { clearTimeout(timer); script.remove(); reject(new Error("map unavailable")); };
      document.head.append(script);
    }).catch(error => { apiPromise = null; throw error; });
    return apiPromise;
  }
  async function loadMap() {
    if (map) { paintCandidate(true); return; }
    if (mapPromise) return mapPromise;
    dialogStatus.textContent = "Загружаем карту…";
    mapPromise = (async () => {
      try {
        const api = await loadApi();
        const first = candidate || walk.getEvents()[0];
        map = new api.YMap(root.querySelector("[data-origin-map]"), {
          location: { center: first ? [first.lng, first.lat] : [37.6176, 55.7558], zoom: first ? 14 : 11 },
        });
        map.addChild(new api.YMapDefaultSchemeLayer({}));
        map.addChild(new api.YMapDefaultFeaturesLayer({}));
        map.addChild(new api.YMapListener({ layer: "any", onClick: (_object, event) => {
          const point = { lng: event.coordinates[0], lat: event.coordinates[1], source: "map" };
          if (validPoint(point)) { candidate = point; paintCandidate(); dialogStatus.textContent = "Проверьте точку и нажмите «Начать отсюда»."; }
        } }));
        root.querySelector("[data-origin-map-retry]").hidden = true;
        dialogStatus.textContent = "Нажмите на карту, чтобы выбрать начальную точку.";
        paintCandidate(true);
      } catch (_) {
        dialogStatus.textContent = "Карта пока недоступна. Можно определить местоположение или указать координаты.";
        root.querySelector("[data-origin-map-retry]").hidden = !root.dataset.mapKey;
        root.querySelector("[data-origin-coordinates]").open = true;
      } finally { mapPromise = null; }
    })();
    return mapPromise;
  }
  function openOrigin(button) {
    opener = button;
    candidate = walk.getOrigin();
    const isRandom = opener === randomButton;
    confirm.textContent = isRandom ? "Построить маршрут" : "Начать отсюда";
    root.querySelector("[data-random-replace-note]").hidden = !isRandom || !walk.getIds().length;
    root.querySelector("[data-origin-results]")?.replaceChildren();
    dialog.showModal();
    root.querySelectorAll("[data-walk-origin-open]").forEach(node => node.setAttribute("aria-expanded", "true"));
    if (button === randomButton) randomButton.setAttribute("aria-expanded", "true");
    paintCandidate(); loadMap();
  }
  function applyOrigin(point) {
    const revision = ++originRevision;
    if (walk.setOrigin(point) === false) return false;
    originMessage("");
    if (!point || !geocoder || point.label) return;
    post(root.dataset.geocodeEndpoint, { point: { lat: point.lat, lng: point.lng } }).then(data => {
      if (revision !== originRevision || !samePoint(walk.getOrigin(), point)) return;
      const label = data.results?.[0]?.label;
      if (typeof label === "string" && label) walk.setOrigin({ ...point, label });
    }).catch(() => {}); // Coordinates remain usable when the address cannot be resolved.
  }
  function setLocateBusy(busy) {
    root.querySelectorAll("[data-walk-locate]").forEach(button => {
      button.disabled = busy;
      if (busy) button.setAttribute("aria-busy", "true"); else button.removeAttribute("aria-busy");
      button.querySelector("span:last-child").textContent = busy ? "Определяем…" : "Моё местоположение";
    });
  }
  function locate() {
    if (!navigator.geolocation) { originMessage("Геолокация недоступна. Выберите начальную точку на карте."); return; }
    const revision = ++geoRevision, inDialog = dialog.open;
    setLocateBusy(true); originMessage("Определяем местоположение…");
    navigator.geolocation.getCurrentPosition(position => {
      if (revision !== geoRevision) return;
      setLocateBusy(false);
      const point = { lat: position.coords.latitude, lng: position.coords.longitude, source: "geolocation" };
      if (!validPoint(point)) { originMessage("Не удалось определить точку. Выберите её на карте."); return; }
      if (inDialog) { candidate = point; paintCandidate(true); dialogStatus.textContent = "Проверьте точку и нажмите «Начать отсюда»."; }
      else { if (applyOrigin(point) !== false) walk.notice("Начальная точка определена"); }
      if (position.coords.accuracy > 1000) originMessage("Местоположение определено приблизительно. Проверьте начальную точку на карте.");
      else originMessage("");
    }, error => {
      if (revision !== geoRevision) return;
      setLocateBusy(false);
      originMessage(error.code === 1 ? "Доступ к местоположению запрещён. Разрешите его в браузере или выберите точку на карте." : "Не удалось определить местоположение. Попробуйте ещё раз или выберите точку на карте.");
    }, { timeout: 10000, maximumAge: 60000, enableHighAccuracy: true });
  }

  root.querySelectorAll("[data-walk-origin-open]").forEach(button => button.addEventListener("click", () => openOrigin(button)));
  root.querySelectorAll("[data-walk-locate]").forEach(button => button.addEventListener("click", locate));
  randomButton.addEventListener("click", () => openOrigin(randomButton));
  const cancelRandom = () => {
    randomRequest?.abort();
    randomMessage("");
  };
  document.addEventListener("kidstime:walk-changed", cancelRandom);
  confirm.addEventListener("click", () => {
    if (!validPoint(candidate)) return;
    if (applyOrigin({ ...candidate }) === false) return;
    dialog.close();
    if (opener === randomButton) generateWalk();
    else walk.notice("Начальная точка выбрана");
  });
  root.querySelector("[data-origin-clear]").addEventListener("click", () => { if (applyOrigin(null) !== false) dialog.close(); });
  root.querySelector("[data-origin-map-retry]").addEventListener("click", loadMap);
  dialog.addEventListener("close", () => {
    geoRevision++; searchRevision++; setLocateBusy(false);
    const searchButton = root.querySelector("[data-origin-search] button");
    if (searchButton) searchButton.disabled = false;
    root.querySelectorAll("[data-walk-origin-open]").forEach(node => node.setAttribute("aria-expanded", "false"));
    randomButton.setAttribute("aria-expanded", "false");
    const returnTo = opener?.isConnected ? opener : root.querySelector("[data-walk-origin-open]");
    returnTo?.focus({ preventScroll: true });
  });
  root.querySelector("[data-origin-coordinate-form]").addEventListener("submit", event => {
    event.preventDefault();
    const form = event.currentTarget;
    const point = { lat: Number(form.elements.lat.value), lng: Number(form.elements.lng.value), source: "map" };
    if (validPoint(point)) { candidate = point; paintCandidate(true); }
  });
  root.querySelector("[data-origin-search]")?.addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget, button = form.querySelector("button");
    const results = root.querySelector("[data-origin-results]");
    const revision = ++searchRevision;
    button.disabled = true; results.replaceChildren(); dialogStatus.textContent = "Ищем адрес…";
    try {
      const data = await post(root.dataset.geocodeEndpoint, { query: form.elements.query.value.trim() });
      if (revision !== searchRevision || !dialog.open) return;
      const points = (Array.isArray(data.results) ? data.results : []).filter(validPoint).slice(0, 5);
      dialogStatus.textContent = points.length ? "Выберите подходящий адрес." : "Адрес не найден. Попробуйте уточнить его или выберите точку на карте.";
      points.forEach(point => {
        const item = document.createElement("button"); item.type = "button"; item.textContent = point.label || pointText(point);
        item.addEventListener("click", () => { candidate = { ...point, source: "address" }; paintCandidate(true); dialogStatus.textContent = "Проверьте точку и нажмите «Начать отсюда»."; });
        results.append(item);
      });
    } catch (_) { if (revision === searchRevision) dialogStatus.textContent = "Поиск адреса временно недоступен. Выберите точку на карте."; }
    finally { if (revision === searchRevision) button.disabled = false; }
  });
  document.addEventListener("kidstime:walk-origin-changed", event => {
    paintOrigin();
    if (event.detail.coordinatesChanged) cancelRandom();
  });
  paintOrigin();
  const personalDialog = root.querySelector("[data-walk-points-dialog]");
  const personalOpener = root.querySelector("[data-walk-points-open]");
  function renderPersonalChoices() {
    const list = root.querySelector("[data-walk-personal-points]");
    const origins = root.querySelector("[data-origin-personal-points]");
    list.replaceChildren(); origins.replaceChildren();
    let points;
    try { points = walk.getPersonalPoints(); }
    catch (_) {
      for (const node of [list, origins]) { const p = document.createElement("p"); p.textContent = "Не удалось открыть сохранённые точки. Проверьте настройки хранения данных в браузере."; node.append(p); }
      return;
    }
    if (!points.length) {
      for (const node of [list, origins]) { const p = document.createElement("p"); p.textContent = "Сохраните свои места на карте, чтобы выбирать их здесь."; node.append(p); }
    }
    points.forEach(point => {
      const ref = walk.places.personalPointRef(point.id);
      const record = document.createElement("div"); record.className = "walk-personal-choice";
      const name = document.createElement("strong"); name.textContent = point.name;
      const address = document.createElement("p"); address.textContent = point.address || pointText(point);
      const actions = document.createElement("div"); actions.className = "walk-personal-choice__actions";
      const add = document.createElement("button"); add.type = "button"; add.className = "secondary-button";
      add.dataset.walkButton = ref; add.dataset.walkDefaultLabel = "+ В маршрут"; add.dataset.walkActiveLabel = "✓ В маршруте";
      add.setAttribute("aria-pressed", "false"); walk.refreshButton(add);
      const start = document.createElement("button"); start.type = "button"; start.className = "secondary-button"; start.textContent = "Начать отсюда";
      start.addEventListener("click", () => {
        if (walk.setOrigin({ lat: point.lat, lng: point.lng, label: point.name, source: "personal", pointId: point.id })) {
          personalDialog.close(); walk.notice("Начальная точка выбрана");
        }
      });
      actions.append(add, start); record.append(name, address, actions); list.append(record);
      const chooseOrigin = document.createElement("button"); chooseOrigin.type = "button"; chooseOrigin.className = "walk-personal-origin-choice";
      chooseOrigin.textContent = point.name;
      chooseOrigin.addEventListener("click", () => {
        candidate = { lat: point.lat, lng: point.lng, label: point.name, source: "personal", pointId: point.id };
        paintCandidate(true); dialogStatus.textContent = "Проверьте начальную точку и нажмите «Начать отсюда».";
      });
      origins.append(chooseOrigin);
    });
  }
  personalOpener.addEventListener("click", () => {
    renderPersonalChoices(); personalDialog.showModal(); personalOpener.setAttribute("aria-expanded", "true");
  });
  root.querySelector("[data-walk-points-close]").addEventListener("click", () => personalDialog.close());
  personalDialog.addEventListener("close", () => { personalOpener.setAttribute("aria-expanded", "false"); personalOpener.focus(); });
  document.addEventListener("kidstime:personal-points-changed", renderPersonalChoices);
  renderPersonalChoices();
  const url = new URL(window.location.href);
  if (url.searchParams.get("random") === "1" && !url.searchParams.has("route")) {
    url.searchParams.delete("random");
    window.history.replaceState(window.history.state, "", url);
    openOrigin(randomButton);
  }
})();
