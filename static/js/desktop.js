(async () => {
  await window.KidsTimeReady;
  // Native dialogs keep focus inside overlays and restore it on dismissal.
  if (typeof HTMLDialogElement !== "undefined" && typeof HTMLDialogElement.prototype.showModal === "function") {
    document.documentElement.classList.add("has-native-dialogs");
  }
  const panelOpeners = new WeakMap();
  document.querySelectorAll("[data-panel-open]").forEach((button) => {
    const panel = document.getElementById(button.dataset.panelOpen);
    if (!panel) return;
    button.addEventListener("click", (event) => {
      if (button.tagName === "A") event.preventDefault();
      const parentPanel = button.closest("dialog");
      panelOpeners.set(panel, parentPanel ? panelOpeners.get(parentPanel) || button : button);
      document.querySelectorAll("dialog[open]").forEach((open) => open.close());
      panel.showModal();
      button.setAttribute("aria-expanded", "true");
    });
    panel.addEventListener("close", () => button.setAttribute("aria-expanded", "false"));
  });

  const tabletViewport = matchMedia("(min-width: 640px) and (max-width: 1023px)");
  const desktopCollections = matchMedia("(min-width: 1024px)");
  const collectionPages = (list, nav, selector, matches = () => true, desktopPageSize = 0) => {
    if (!list || !nav) return { refresh() {} };
    let page = 1;
    const refresh = (reset = false) => {
      if (reset) page = 1;
      const all = [...list.querySelectorAll(selector)];
      const eligible = all.filter(matches);
      const pageSize = tabletViewport.matches ? 6 : (desktopCollections.matches ? desktopPageSize : 0);
      const pages = pageSize ? Math.max(1, Math.ceil(eligible.length / pageSize)) : 1;
      page = Math.min(page, pages);
      const visible = new Set(pageSize ? eligible.slice((page - 1) * pageSize, page * pageSize) : eligible);
      all.forEach((item) => { item.hidden = !visible.has(item); });
      nav.hidden = !pageSize || pages < 2;
      nav.replaceChildren();
      if (nav.hidden) return;
      const button = (label, value, step = false) => {
        const node = document.createElement("button"); node.type = "button"; node.textContent = label;
        node.dataset.collectionPage = String(value); node.className = step ? "pagination__step" : "pagination__number";
        node.disabled = value < 1 || value > pages;
        if (!step) node.setAttribute("aria-label", `Страница ${value}`);
        if (!step && value === page) { node.classList.add("is-current"); node.setAttribute("aria-current", "page"); }
        return node;
      };
      nav.append(button("Назад", page - 1, true));
      const start = Math.max(1, Math.min(page - 2, pages - 4));
      const numbers = new Set([1, pages]);
      for (let number = start; number <= Math.min(pages, start + 4); number++) numbers.add(number);
      let previous = 0;
      [...numbers].sort((a, b) => a - b).forEach(number => {
        if (number > previous + 1) {
          const ellipsis = document.createElement("span"); ellipsis.textContent = "…"; ellipsis.setAttribute("aria-hidden", "true"); nav.append(ellipsis);
        }
        nav.append(button(String(number), number)); previous = number;
      });
      nav.append(button("Далее", page + 1, true));
      const count = document.createElement("small"); count.textContent = `Страница ${page} из ${pages}`; nav.append(count);
    };
    nav.addEventListener("click", (event) => {
      const button = event.target.closest("[data-collection-page]");
      if (!button || button.disabled) return;
      page = Number(button.dataset.collectionPage); refresh();
      nav.querySelector('[aria-current="page"]')?.focus({preventScroll: true});
      list.scrollIntoView({block: "start", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth"});
    });
    tabletViewport.addEventListener("change", () => refresh());
    desktopCollections.addEventListener("change", () => refresh());
    return { refresh };
  };
  const favoritePages = collectionPages(document.querySelector("[data-device-favorites]"), document.querySelector("[data-favorite-pages]"), ".event-card", (card) => card.dataset.favoriteMatch !== "false", 9);
  document.addEventListener("kidstime:favorite-cards-filtered", () => favoritePages.refresh());
  favoritePages.refresh();
  document.querySelectorAll("dialog").forEach((dialog) => {
    dialog.addEventListener("close", () => {
      if (document.querySelector("dialog[open]")) return;
      const opener = panelOpeners.get(dialog);
      if (opener?.getClientRects().length && !opener.closest("dialog:not([open])")) opener.focus({preventScroll: true});
    });
    dialog.querySelectorAll("[data-panel-close]").forEach((button) => button.addEventListener("click", () => dialog.close()));
    dialog.addEventListener("click", (event) => {
      const rect = dialog.getBoundingClientRect();
      if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) dialog.close();
    });
  });

  document.querySelectorAll("[data-avatar-form]").forEach((form) => {
    const input = form.querySelector("[data-avatar-input]");
    const submit = form.querySelector("[data-avatar-submit]");
    submit.hidden = true;
    input.addEventListener("change", () => {
      if (!input.files.length) return;
      if (input.files[0].size > 5 * 1024 * 1024) {
        window.KidsTimeWalk?.notice("Выберите фото размером до 5 МБ.");
        input.value = "";
        return;
      }
      form.requestSubmit();
    });
    form.addEventListener("submit", () => { form.setAttribute("aria-busy", "true"); });
  });

  document.querySelectorAll("[data-format-choices]").forEach((choices) => {
    const native = choices.closest(".filters-form").querySelector("[data-format-select]");
    native.querySelector("select").disabled = true;
    native.hidden = true;
    choices.hidden = false;
    choices.querySelectorAll("input").forEach((input) => { input.disabled = false; });
  });

  document.querySelectorAll("[data-time-filter]").forEach((filter) => {
    const lower = filter.querySelector("[data-time-min]");
    const upper = filter.querySelector("[data-time-max]");
    const from = filter.querySelector("[name=time_from]");
    const until = filter.querySelector("[name=time_until]");
    const minutes = (value, fallback) => /^\d{2}:\d{2}$/.test(value) ? Number(value.slice(0,2)) * 60 + Number(value.slice(3)) : fallback;
    const clock = (value) => `${String(Math.floor(value / 60)).padStart(2,"0")}:${String(value % 60).padStart(2,"0")}`;
    const selection = filter.querySelector("[data-time-selection]");
    const describe = () => {
      lower.setAttribute("aria-valuetext", clock(Number(lower.value)));
      upper.setAttribute("aria-valuetext", clock(Number(upper.value)));
      if (selection) { selection.hidden = !from.value && !until.value; selection.textContent = `${from.value || "08:00"} — ${until.value || "22:00"}`; }
    };
    const sync = () => {
      const start = minutes(from.value, 480), end = minutes(until.value, 1320);
      const fitsSlider = (value) => value >= 480 && value <= 1320 && value % 30 === 0;
      filter.classList.toggle("has-time-slider", start <= end && fitsSlider(start) && fitsSlider(end));
      lower.value = start; upper.value = end; describe();
    };
    lower.addEventListener("input", () => { lower.value = Math.min(Number(lower.value), Number(upper.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); describe(); });
    upper.addEventListener("input", () => { upper.value = Math.max(Number(upper.value), Number(lower.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); describe(); });
    from.addEventListener("change", sync); until.addEventListener("change", sync); sync();
  });

  const storageKey = "kidstime:saved-walks";
  const maximumRoutes = 20;
  const walk = window.KidsTimeWalk;
  const notice = (text) => walk?.notice(text);
  const normalizeIds = walk.normalizeIds;
  const readRoutes = () => {
    try {
      const values = JSON.parse(localStorage.getItem(storageKey) || "[]");
      return walk.places.normalizeSavedWalks(values);
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
    if (saved) { if (walk.restore(saved.ids, saved.origin_id)) activeRouteId = saved.id; }
    else if (wanted) notice("Сохранённый маршрут не найден в этом браузере.");
    const dialog = root.querySelector("[data-route-dialog]");
    const form = root.querySelector("[data-save-walk-form]");
    const saveButton = root.querySelector("[data-save-walk]");
    const deleteButton = root.querySelector("[data-delete-walk]");
    const update = () => {
      const route = readRoutes().find((item) => item.id === activeRouteId);
      root.querySelectorAll("[data-walk-title]").forEach((node) => { node.textContent = route?.name || "Маршрут на день"; });
      root.classList.toggle("is-saved", Boolean(route));
      saveButton.disabled = !walk.isComplete();
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
      if (!name || !ids.length || !walk.isComplete() || (index < 0 && routes.length >= maximumRoutes)) {
        error.textContent = !name ? "Укажите название маршрута." : !ids.length ? "Добавьте доступные места в маршрут." : !walk.isComplete() ? "Проверьте доступность точек и выберите начало маршрута." : `Можно сохранить до ${maximumRoutes} маршрутов. Удалите один из прежних.`;
        error.hidden = false;
        return;
      }
      const id = index >= 0 ? activeRouteId : crypto.randomUUID();
      const record = { id, name: name.slice(0, 80), ids };
      if (walk.getOriginRef()) record.origin_id = walk.getOriginRef();
      const createdAt = index >= 0 ? routes[index].created_at : new Date().toISOString();
      if (createdAt) record.created_at = createdAt;
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
    document.addEventListener("kidstime:walk-origin-changed", update);
    document.addEventListener("kidstime:walk-load-error", update);
    document.addEventListener("kidstime:saved-walks-changed", update);
    update();
  }

  const savedRoot = document.querySelector("[data-saved-walks]");
  const savedPages = collectionPages(savedRoot?.querySelector("[data-saved-walks-list]"), savedRoot?.querySelector("[data-saved-walk-pages]"), ".saved-route");
  let sequence = 0;
  const renderRoutes = async () => {
    if (!savedRoot) return;
    const current = ++sequence;
    const list = savedRoot.querySelector("[data-saved-walks-list]");
    list.replaceChildren();
    const routes = readRoutes();
    savedRoot.classList.toggle("is-empty", routes.length === 0);
    if (!routes.length) { list.append(savedRoot.querySelector("[data-saved-walks-empty]").content.cloneNode(true)); savedPages.refresh(); return; }
    for (const route of routes) {
      const card = document.createElement("article"); card.className = "saved-route";
      const link = document.createElement("a"); link.href = `${savedRoot.dataset.walkUrl}?route=${encodeURIComponent(route.id)}`;
      const cover = document.createElement("div"); cover.className = "saved-route__cover";
      const badge = document.createElement("span"); badge.className = "saved-route__badge";
      const totalPoints = route.ids.length + Number(Boolean(route.origin_id));
      const number = document.createElement("span"); number.className = "saved-route__number"; number.textContent = String(totalPoints); number.setAttribute("aria-hidden", "true");
      const count = document.createElement("span"); count.className = "sr-only"; count.textContent = `Точек в маршруте: ${totalPoints}`;
      badge.append(number, count);
      const body = document.createElement("div"); body.className = "saved-route__body";
      const heading = document.createElement("h2"); heading.textContent = route.name; heading.title = route.name;
      const meta = document.createElement("p"); meta.className = "saved-route__meta";
      const fact = (name, label) => {
        const node = document.createElement("span"); node.className = `saved-route__fact saved-route__fact--${name}`;
        const icon = document.createElement("span"); icon.className = `ui-icon ui-icon--${name === "date" ? "calendar" : "child"}`; icon.setAttribute("aria-hidden", "true");
        const value = document.createElement("span"); value.className = "saved-route__value"; value.textContent = "Уточняется";
        node.setAttribute("aria-label", `${label}: уточняется`); node.append(icon, value); meta.append(node);
        return (text, description = text) => { value.textContent = text; node.title = description; node.setAttribute("aria-label", `${label}: ${description}`); };
      };
      const setDate = fact("date", "Даты событий");
      const setAge = fact("age", "Возрастное ограничение");
      const availability = document.createElement("p"); availability.className = "saved-route__availability"; availability.hidden = true;
      body.append(heading, meta, availability); link.append(cover, badge, body);
      const remove = document.createElement("button"); remove.className = "saved-route__remove"; remove.type = "button"; remove.textContent = "Удалить";
      remove.hidden = true; remove.id = `remove-route-${route.id}`; remove.setAttribute("aria-label", `Удалить маршрут «${route.name}»`);
      remove.addEventListener("click", () => { if (window.confirm(`Удалить маршрут «${route.name}»?`)) writeRoutes(readRoutes().filter((item) => item.id !== route.id)); });
      const actions = document.createElement("button"); actions.className = "saved-route__actions"; actions.type = "button"; actions.textContent = "⋯";
      actions.setAttribute("aria-label", `Действия с маршрутом «${route.name}»`); actions.setAttribute("aria-expanded", "false"); actions.setAttribute("aria-controls", remove.id);
      const reveal = (open) => { card.classList.toggle("is-revealed", open); actions.setAttribute("aria-expanded", String(open)); remove.hidden = !open; };
      actions.addEventListener("click", () => reveal(!card.classList.contains("is-revealed")));
      card.addEventListener("keydown", (event) => { if (event.key === "Escape") { reveal(false); actions.focus(); } });
      let touch = null;
      let suppressClick = false;
      card.addEventListener("pointerdown", (event) => {
        if (event.pointerType !== "mouse" && matchMedia("(max-width: 639px)").matches) touch = { x: event.clientX, y: event.clientY };
      });
      card.addEventListener("pointercancel", () => { touch = null; });
      card.addEventListener("pointerup", (event) => {
        if (!touch) return;
        const dx = event.clientX - touch.x; const dy = event.clientY - touch.y; touch = null;
        if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.5) {
          reveal(dx < 0); suppressClick = true;
          setTimeout(() => { suppressClick = false; }, 500);
        }
      });
      link.addEventListener("click", (event) => { if (suppressClick) { event.preventDefault(); suppressClick = false; } });
      card.append(link, actions, remove); list.append(card);
      walk.resolvePoints(route.ids, savedRoot.dataset.endpoint).then((events) => {
        if (current !== sequence) return;
        const origin = route.origin_id ? walk.places.resolvePersonalOrigin(route.origin_id, walk.getPersonalPoints()) : null;
        const available = events.length + Number(Boolean(origin));
        const complete = available === totalPoints;
        const catalog = events.filter(item => item.kind !== "personal");
        meta.hidden = !catalog.length;
        const dates = [...new Set(catalog.map((item) => typeof item.date === "string" && item.date.trim() ? item.date.trim() : "Уточняется"))];
        if (!complete && !dates.includes("Уточняется")) dates.push("Уточняется");
        setDate(dates.join(" · ") || "Уточняется");
        const ages = catalog.map((item) => typeof item.age === "string" && /^\d+\+$/.test(item.age) ? Number.parseInt(item.age, 10) : null);
        setAge(complete && ages.length && ages.every((age) => age !== null) ? `${Math.max(...ages)}+` : "Уточняется");
        if (!complete) {
          availability.textContent = `Доступно ${available} из ${totalPoints} точек`;
          availability.hidden = false;
        }
        const photo = events.find((item) => item.cover)?.cover;
        if (photo) { const image = document.createElement("img"); image.src = photo; image.alt = ""; image.loading = "lazy"; image.referrerPolicy = "no-referrer"; cover.append(image); }
      }).catch(() => {
        if (current !== sequence) return;
        availability.textContent = "Не удалось проверить точки. Откройте маршрут ещё раз.";
        availability.hidden = false;
      });
    }
    savedPages.refresh();
  };
  document.addEventListener("kidstime:saved-walks-changed", () => { refreshCounts(); renderRoutes(); });
  document.addEventListener("kidstime:personal-points-changed", renderRoutes);
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) document.dispatchEvent(new Event("kidstime:saved-walks-changed"));
    if (event.key === "kidstime:favorites") refreshCounts();
  });
  refreshCounts(); renderRoutes();
})();
