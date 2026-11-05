(() => {
  const root = document.querySelector("[data-walk-root]");
  const walk = window.KidsTimeWalk;
  if (!root || !walk) return;
  const list = root.querySelector("[data-walk-list]");
  const dialog = root.querySelector("[data-walk-origin-dialog]");
  const confirm = root.querySelector("[data-origin-confirm]");
  const selection = root.querySelector("[data-origin-selection]");
  const dialogStatus = root.querySelector("[data-origin-dialog-status]");
  const originStatus = root.querySelector("[data-walk-origin-status]");
  const retry = root.querySelector("[data-walk-times-retry]");
  const timeNote = root.querySelector("[data-walk-time-note]");
  const modeInput = root.querySelector("[data-walk-mode]");
  const modeNames = { walking: "пешком", driving: "на авто", transit: "на транспорте" };
  const types = { walking: "pd", driving: "auto", transit: "mt" };
  const enabled = root.dataset.routingEnabled === "true";
  const geocoder = root.dataset.geocoderEnabled === "true";
  const csrf = root.querySelector("[name=csrfmiddlewaretoken]")?.value || "";
  const validPoint = p => p && Number.isFinite(p.lat) && Number.isFinite(p.lng) && Math.abs(p.lat) <= 90 && Math.abs(p.lng) <= 180;
  const samePoint = (a, b) => validPoint(a) && validPoint(b) && a.lat === b.lat && a.lng === b.lng;
  const pointText = p => `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}`;
  const duration = seconds => {
    const minutes = Math.ceil(seconds / 60);
    if (!minutes) return "Менее 1 мин";
    return minutes < 60 ? `${minutes} мин` : `${Math.floor(minutes / 60)} ч${minutes % 60 ? ` ${minutes % 60} мин` : ""}`;
  };
  const routeUrl = (from, to) => {
    const url = new URL("https://yandex.ru/maps/");
    url.searchParams.set("rtext", `${from.lat},${from.lng}~${to.lat},${to.lng}`);
    url.searchParams.set("rtt", types[walk.getMode()]);
    return url.href;
  };
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

  let estimateSequence = 0;
  let estimatesController;
  let bindings = [];
  const cache = new Map(); // Page-memory only; origin coordinates never enter browser storage.
  function cancelEstimates() {
    estimateSequence++;
    estimatesController?.abort();
    retry.disabled = false;
    retry.removeAttribute("aria-busy");
  }
  function addLegs(events) {
    list.querySelectorAll(".walk-leg").forEach(node => node.remove());
    bindings = [];
    const origin = walk.getOrigin();
    events.forEach((event, i) => {
      const item = list.querySelector(`[data-walk-event-id="${event.id}"]`);
      if (!item) return;
      const from = i ? events[i - 1] : origin;
      const leg = document.createElement("div"); leg.className = "walk-leg";
      const label = document.createElement(from ? "a" : "button");
      label.className = "walk-leg__label";
      if (from) {
        label.href = routeUrl(from, event); label.target = "_blank"; label.rel = "noopener";
        label.textContent = enabled ? "Рассчитываем…" : "Уточнить время ↗";
        const binding = { from: i ? String(events[i - 1].id) : "origin", to: String(event.id), label };
        bindings.push(binding);
        label.setAttribute("aria-label", `Время пути до «${event.title}»: открыть в Яндекс Картах`);
      } else {
        label.type = "button"; label.textContent = "Выбрать старт";
        label.dataset.walkOriginOpen = "";
        label.setAttribute("aria-controls", dialog.id); label.setAttribute("aria-haspopup", "dialog");
        label.setAttribute("aria-label", "Выбрать начальную точку для расчёта времени");
        label.addEventListener("click", () => openOrigin(label));
      }
      leg.append(label); item.before(leg);
    });
  }
  function setNote(text, attribution = false) {
    timeNote.textContent = text;
    if (attribution) {
      const link = document.createElement("a"); link.href = "https://yandex.ru/maps/";
      link.textContent = "Яндекс Карты"; link.target = "_blank"; link.rel = "noopener";
      timeNote.append(document.createTextNode(" "), link);
    }
  }
  function applyTimes(data) {
    if (data.mode !== walk.getMode() || !Array.isArray(data.legs) || data.legs.length !== bindings.length) throw new Error("invalid route");
    const valid = data.legs.every((leg, i) => leg.from_id === bindings[i].from && leg.to_id === bindings[i].to && (leg.seconds === null || (Number.isFinite(leg.seconds) && leg.seconds >= 0)));
    if (!valid) throw new Error("invalid route");
    data.legs.forEach((leg, i) => {
      const label = bindings[i].label;
      label.textContent = leg.seconds === null ? "Путь не найден" : duration(leg.seconds);
      label.classList.toggle("is-unavailable", leg.seconds === null);
      label.title = `${modeNames[walk.getMode()]} · ${label.textContent} · Яндекс Карты`;
      label.setAttribute("aria-label", `${label.title}. Открыть этот участок в Яндекс Картах`);
    });
    if (data.legs.every(leg => leg.seconds !== null)) {
      const total = data.legs.reduce((sum, leg) => sum + leg.seconds, 0);
      setNote(`${walk.getOrigin() ? "В дороге" : "Между выбранными местами"}: ${duration(total)}, ${modeNames[walk.getMode()]}. Оценка на текущее время, без учёта посещения мест.`, true);
    } else setNote("Для части участков путь не найден. Проверьте точки в Яндекс Картах.", true);
  }
  async function refreshTimes(force = false) {
    cancelEstimates();
    const sequence = estimateSequence;
    if (root.getAttribute("aria-busy") === "true") return;
    const events = walk.getEvents();
    addLegs(events);
    retry.hidden = !enabled || !bindings.length;
    if (!events.length) { setNote(""); return; }
    if (!bindings.length) { setNote("Выберите начальную точку, чтобы рассчитать путь до первого места."); return; }
    if (!enabled) { setNote("Время в пути можно посмотреть в Яндекс Картах."); return; }
    const origin = walk.getOrigin();
    const payload = { ids: events.map(e => e.id), mode: walk.getMode(), origin: origin ? { lat: origin.lat, lng: origin.lng } : null };
    const key = JSON.stringify({ ...payload, points: events.map(e => [e.lat, e.lng]) });
    const cached = cache.get(key);
    if (!force && cached && Date.now() - cached.at < 300000) { applyTimes(cached.data); return; }
    estimatesController = new AbortController();
    retry.disabled = true; retry.setAttribute("aria-busy", "true");
    setNote("Рассчитываем время в пути…");
    try {
      const data = await post(root.dataset.timesEndpoint, payload, estimatesController.signal);
      if (sequence !== estimateSequence) return;
      applyTimes(data);
      if (cache.size >= 20) cache.delete(cache.keys().next().value);
      cache.set(key, { at: Date.now(), data });
    } catch (error) {
      if (sequence !== estimateSequence) return;
      if (error.status === 409) { walk.reload(); return; }
      bindings.forEach(({ label }) => { label.textContent = "Время недоступно ↗"; label.classList.add("is-unavailable"); });
      setNote(error.status === 429 ? "Слишком частые расчёты. Повторите позже или откройте маршрут в Яндекс Картах." : "Не удалось рассчитать время. Можно повторить расчёт или открыть маршрут в Яндекс Картах.");
    } finally {
      if (sequence === estimateSequence) { retry.disabled = false; retry.removeAttribute("aria-busy"); }
    }
  }

  let candidate = null;
  let map, marker, apiPromise, mapPromise, opener;
  let originRevision = 0, geoRevision = 0, searchRevision = 0;
  function paintOrigin() {
    const point = walk.getOrigin();
    root.querySelector("[data-walk-origin-title]").textContent = point?.source === "geolocation" ? "Ваше текущее местоположение" : "Начальная точка";
    root.querySelector("[data-walk-origin-label]").textContent = point ? (point.label || pointText(point)) : "Выбрать на карте";
    root.querySelector("[data-origin-clear]").hidden = !point;
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
    root.querySelector("[data-origin-results]")?.replaceChildren();
    dialog.showModal();
    root.querySelectorAll("[data-walk-origin-open]").forEach(node => node.setAttribute("aria-expanded", "true"));
    paintCandidate(); loadMap();
  }
  function applyOrigin(point) {
    const revision = ++originRevision;
    walk.setOrigin(point);
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
      else { applyOrigin(point); walk.notice("Начальная точка определена"); }
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
  confirm.addEventListener("click", () => { if (validPoint(candidate)) { applyOrigin({ ...candidate }); dialog.close(); walk.notice("Начальная точка выбрана"); } });
  root.querySelector("[data-origin-clear]").addEventListener("click", () => { applyOrigin(null); dialog.close(); });
  root.querySelector("[data-origin-map-retry]").addEventListener("click", loadMap);
  dialog.addEventListener("close", () => {
    geoRevision++; searchRevision++; setLocateBusy(false);
    const searchButton = root.querySelector("[data-origin-search] button");
    if (searchButton) searchButton.disabled = false;
    root.querySelectorAll("[data-walk-origin-open]").forEach(node => node.setAttribute("aria-expanded", "false"));
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
  modeInput.addEventListener("change", () => walk.setMode(modeInput.value));
  retry.addEventListener("click", () => refreshTimes(true));
  document.addEventListener("kidstime:walk-loaded", () => refreshTimes());
  document.addEventListener("kidstime:walk-mode-changed", () => refreshTimes());
  document.addEventListener("kidstime:walk-origin-changed", event => { paintOrigin(); if (!walk.getOrigin()) cache.clear(); if (event.detail?.coordinatesChanged !== false) refreshTimes(); });
  document.addEventListener("kidstime:walk-loading", () => { cancelEstimates(); bindings.forEach(({ label }) => { label.textContent = "Обновляем…"; }); retry.hidden = true; });
  document.addEventListener("kidstime:walk-load-error", () => { cancelEstimates(); setNote(""); retry.hidden = true; });
  paintOrigin(); refreshTimes();
})();
