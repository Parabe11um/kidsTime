(() => {
  // Native dialogs keep focus inside overlays and restore it on dismissal.
  document.querySelectorAll("[data-panel-open]").forEach((button) => {
    const panel = document.getElementById(button.dataset.panelOpen);
    if (!panel) return;
    button.addEventListener("click", () => {
      document.querySelectorAll("dialog[open]").forEach((open) => open.close());
      panel.showModal();
      button.setAttribute("aria-expanded", "true");
    });
    panel.addEventListener("close", () => button.setAttribute("aria-expanded", "false"));
  });
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.querySelectorAll("[data-panel-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
    });
  });

  document.querySelectorAll("[data-time-filter]").forEach((filter) => {
    const lower = filter.querySelector("[data-time-min]");
    const upper = filter.querySelector("[data-time-max]");
    const from = filter.querySelector("[name=time_from]");
    const until = filter.querySelector("[name=time_until]");
    const minutes = (value, fallback) => /^\d{2}:\d{2}$/.test(value) ? Number(value.slice(0,2)) * 60 + Number(value.slice(3)) : fallback;
    const clock = (value) => `${String(Math.floor(value / 60)).padStart(2,"0")}:${String(value % 60).padStart(2,"0")}`;
    const sync = () => { lower.value = minutes(from.value, 480); upper.value = minutes(until.value, 1320); };
    lower.addEventListener("input", () => { lower.value = Math.min(Number(lower.value), Number(upper.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); });
    upper.addEventListener("input", () => { upper.value = Math.max(Number(upper.value), Number(lower.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); });
    from.addEventListener("change", sync); until.addEventListener("change", sync); sync();
  });

  const storageKey = "kidstime:saved-walks";
  const maximumRoutes = 20;
  const walk = window.KidsTimeWalk;
  const notice = (text) => walk?.notice(text);
  const normalizeIds = (ids) => [...new Set((Array.isArray(ids) ? ids : []).map(String).filter((id) => /^[1-9]\d{0,18}$/.test(id)))].slice(0, 9);
  const readRoutes = () => {
    try {
      const values = JSON.parse(localStorage.getItem(storageKey) || "[]");
      if (!Array.isArray(values)) return [];
      const unique = new Set();
      return values.filter((route) => {
        if (!route || typeof route !== "object" || typeof route.id !== "string" || !/^[\w-]{1,80}$/.test(route.id) || unique.has(route.id)) return false;
        unique.add(route.id);
        return typeof route.name === "string" && route.name.trim() && normalizeIds(route.ids).length;
      }).slice(0, maximumRoutes).map((route) => ({ id: route.id, name: route.name.trim().slice(0, 80), ids: normalizeIds(route.ids) }));
    } catch (_) { return []; }
  };
  const writeRoutes = (routes) => {
    try {
      localStorage.setItem(storageKey, JSON.stringify(routes));
      document.dispatchEvent(new Event("kidstime:saved-walks-changed"));
      return true;
    } catch (_) {
      notice("Не удалось сохранить маршрут. Разрешите сохранение данных в браузере.");
      return false;
    }
  };
  const refreshCounts = () => {
    document.querySelectorAll("[data-saved-walk-count]").forEach((node) => { node.textContent = String(readRoutes().length); });
    const count = window.KidsTimeFavorites?.getCount();
    if (Number.isInteger(count)) document.querySelectorAll("[data-favorite-count]").forEach((node) => { node.textContent = String(count); });
  };
  // Use the live selection for both guests and signed-in users.
  document.addEventListener("kidstime:favorites-changed", (event) => {
    if (event.detail?.count !== undefined) document.querySelectorAll("[data-favorite-count]").forEach((node) => { node.textContent = String(event.detail.count); });
  });

  const root = document.querySelector("[data-walk-root]");
  let activeRouteId = null;
  if (root && walk) {
    const wanted = new URLSearchParams(location.search).get("route");
    const saved = readRoutes().find((route) => route.id === wanted);
    if (saved) { activeRouteId = saved.id; walk.replaceIds(saved.ids); }
    else if (wanted) notice("Сохранённый маршрут не найден в этом браузере.");
    const dialog = root.querySelector("[data-route-dialog]");
    const form = root.querySelector("[data-save-walk-form]");
    const saveButton = root.querySelector("[data-save-walk]");
    const deleteButton = root.querySelector("[data-delete-walk]");
    const update = () => {
      const route = readRoutes().find((item) => item.id === activeRouteId);
      root.querySelectorAll("[data-walk-title]").forEach((node) => { node.textContent = route?.name || "Маршрут на день"; });
      saveButton.disabled = !walk.getEvents().length;
      deleteButton.hidden = !route;
    };
    saveButton.addEventListener("click", () => {
      form.elements.name.value = readRoutes().find((route) => route.id === activeRouteId)?.name || "";
      root.querySelector("[data-save-walk-error]").hidden = true;
      dialog.showModal();
      form.elements.name.focus();
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const name = form.elements.name.value.trim();
      const ids = normalizeIds(walk.getEvents().map((item) => item.id));
      const routes = readRoutes();
      const index = routes.findIndex((route) => route.id === activeRouteId);
      const error = root.querySelector("[data-save-walk-error]");
      if (!name || !ids.length || (index < 0 && routes.length >= maximumRoutes)) {
        error.textContent = !name ? "Укажите название маршрута." : !ids.length ? "Добавьте доступные места в маршрут." : `Можно сохранить до ${maximumRoutes} маршрутов. Удалите один из прежних.`;
        error.hidden = false;
        return;
      }
      const id = index >= 0 ? activeRouteId : crypto.randomUUID();
      const record = { id, name: name.slice(0, 80), ids };
      if (index >= 0) routes[index] = record; else routes.unshift(record);
      if (!writeRoutes(routes)) {
        error.textContent = "Не удалось записать маршрут в браузере."; error.hidden = false; return;
      }
      activeRouteId = id;
      const url = new URL(location.href); url.searchParams.set("route", id); history.replaceState(null, "", url);
      update(); dialog.close(); notice("Маршрут сохранён");
    });
    deleteButton.addEventListener("click", () => {
      if (!window.confirm("Удалить сохранённый маршрут?")) return;
      if (!writeRoutes(readRoutes().filter((route) => route.id !== activeRouteId))) return;
      activeRouteId = null;
      const url = new URL(location.href); url.searchParams.delete("route"); history.replaceState(null, "", url);
      update(); notice("Сохранённый маршрут удалён");
    });
    document.addEventListener("kidstime:walk-loaded", update);
    document.addEventListener("kidstime:walk-loading", update);
    document.addEventListener("kidstime:saved-walks-changed", update);
    update();
  }

  const savedRoot = document.querySelector("[data-saved-walks]");
  let sequence = 0;
  const renderRoutes = async () => {
    if (!savedRoot) return;
    const current = ++sequence;
    const list = savedRoot.querySelector("[data-saved-walks-list]");
    list.replaceChildren();
    const routes = readRoutes();
    if (!routes.length) { list.append(savedRoot.querySelector("[data-saved-walks-empty]").content.cloneNode(true)); return; }
    for (const route of routes) {
      const card = document.createElement("article"); card.className = "saved-route";
      const link = document.createElement("a"); link.href = `${savedRoot.dataset.walkUrl}?route=${encodeURIComponent(route.id)}`;
      const cover = document.createElement("div"); cover.className = "saved-route__cover";
      const heading = document.createElement("h2"); heading.textContent = route.name;
      const count = document.createElement("p"); count.textContent = `Мест в маршруте: ${route.ids.length}`;
      link.append(cover, heading, count);
      const remove = document.createElement("button"); remove.className = "saved-route__remove"; remove.type = "button"; remove.textContent = "Удалить";
      remove.setAttribute("aria-label", `Удалить маршрут «${route.name}»`);
      remove.addEventListener("click", () => { if (window.confirm(`Удалить маршрут «${route.name}»?`)) writeRoutes(readRoutes().filter((item) => item.id !== route.id)); });
      card.append(link, remove); list.append(card);
      fetch(`${savedRoot.dataset.endpoint}?ids=${encodeURIComponent(route.ids.join(","))}`, { headers: { Accept: "application/json" } }).then((response) => {
        if (!response.ok) throw new Error("unavailable"); return response.json();
      }).then((payload) => {
        if (current !== sequence) return;
        const events = Array.isArray(payload.results) ? payload.results : [];
        count.textContent = events.length === route.ids.length ? `Мест в маршруте: ${events.length}` : `Доступно мест: ${events.length} из ${route.ids.length}`;
        const photo = events.find((item) => item.cover)?.cover;
        if (photo) { const image = document.createElement("img"); image.src = photo; image.alt = ""; image.loading = "lazy"; image.referrerPolicy = "no-referrer"; cover.append(image); }
      }).catch(() => { if (current === sequence) count.textContent = "Не удалось проверить доступность мест. Откройте маршрут ещё раз."; });
    }
  };
  document.addEventListener("kidstime:saved-walks-changed", () => { refreshCounts(); renderRoutes(); });
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) document.dispatchEvent(new Event("kidstime:saved-walks-changed"));
    if (event.key === "kidstime:favorites") refreshCounts();
  });
  refreshCounts(); renderRoutes();
})();
