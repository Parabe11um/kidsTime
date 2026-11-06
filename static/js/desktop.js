(() => {
  // Native dialogs keep focus inside overlays and restore it on dismissal.
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

  const desktopFilters = matchMedia("(min-width: 1024px)");
  document.querySelectorAll(".filters-form").forEach((form) => {
    const native = form.querySelector("[data-format-select]");
    const choices = form.querySelector("[data-format-choices]");
    if (!native || !choices) return;
    const select = native.querySelector("select");
    const radios = [...choices.querySelectorAll("input")];
    const sync = () => {
      const desktop = desktopFilters.matches;
      native.hidden = desktop; select.disabled = desktop; choices.hidden = !desktop;
      radios.forEach((radio) => { radio.disabled = !desktop; radio.checked = radio.value === select.value; });
    };
    radios.forEach((radio) => radio.addEventListener("change", () => { if (radio.checked) select.value = radio.value; }));
    select.addEventListener("change", sync);
    desktopFilters.addEventListener("change", sync); sync();
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
    const sync = () => { lower.value = minutes(from.value, 480); upper.value = minutes(until.value, 1320); describe(); };
    lower.addEventListener("input", () => { lower.value = Math.min(Number(lower.value), Number(upper.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); describe(); });
    upper.addEventListener("input", () => { upper.value = Math.max(Number(upper.value), Number(lower.value)); from.value = clock(Number(lower.value)); until.value = clock(Number(upper.value)); describe(); });
    from.addEventListener("change", sync); until.addEventListener("change", sync); sync();
    filter.classList.add("has-time-slider");
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
      }).slice(0, maximumRoutes).map((route) => {
        const record = { id: route.id, name: route.name.trim().slice(0, 80), ids: normalizeIds(route.ids) };
        if (typeof route.created_at === "string" && /^\d{4}-\d{2}-\d{2}T/.test(route.created_at) && Number.isFinite(Date.parse(route.created_at))) record.created_at = route.created_at;
        return record;
      });
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
      root.classList.toggle("is-saved", Boolean(route));
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
    if (!routes.length) { list.append(savedRoot.querySelector("[data-saved-walks-empty]").content.cloneNode(true)); savedPages.refresh(); return; }
    for (const route of routes) {
      const card = document.createElement("article"); card.className = "saved-route";
      const link = document.createElement("a"); link.href = `${savedRoot.dataset.walkUrl}?route=${encodeURIComponent(route.id)}`;
      const cover = document.createElement("div"); cover.className = "saved-route__cover";
      const badge = document.createElement("span"); badge.className = "saved-route__badge"; badge.textContent = String(route.ids.length); badge.setAttribute("aria-hidden", "true");
      const body = document.createElement("div"); body.className = "saved-route__body";
      const heading = document.createElement("h2"); heading.textContent = route.name;
      const meta = document.createElement("p"); meta.className = "saved-route__meta";
      const count = document.createElement("span"); count.textContent = `Мест: ${route.ids.length}`;
      if (route.created_at) {
        const date = document.createElement("time"); date.dateTime = route.created_at;
        date.textContent = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long" }).format(new Date(route.created_at));
        meta.append(date);
      }
      meta.append(count); body.append(heading, meta); link.append(cover, badge, body);
      const remove = document.createElement("button"); remove.className = "saved-route__remove"; remove.type = "button"; remove.textContent = "Удалить";
      remove.setAttribute("aria-label", `Удалить маршрут «${route.name}»`);
      remove.addEventListener("click", () => { if (window.confirm(`Удалить маршрут «${route.name}»?`)) writeRoutes(readRoutes().filter((item) => item.id !== route.id)); });
      const actions = document.createElement("button"); actions.className = "saved-route__actions"; actions.type = "button"; actions.textContent = "⋯";
      actions.setAttribute("aria-label", `Действия с маршрутом «${route.name}»`); actions.setAttribute("aria-expanded", "false");
      const reveal = (open) => { card.classList.toggle("is-revealed", open); actions.setAttribute("aria-expanded", String(open)); };
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
      fetch(`${savedRoot.dataset.endpoint}?ids=${encodeURIComponent(route.ids.join(","))}`, { headers: { Accept: "application/json" } }).then((response) => {
        if (!response.ok) throw new Error("unavailable"); return response.json();
      }).then((payload) => {
        if (current !== sequence) return;
        const events = Array.isArray(payload.results) ? payload.results : [];
        count.textContent = events.length === route.ids.length ? `Мест: ${events.length}` : `Доступно: ${events.length} из ${route.ids.length}`;
        const photo = events.find((item) => item.cover)?.cover;
        if (photo) { const image = document.createElement("img"); image.src = photo; image.alt = ""; image.loading = "lazy"; image.referrerPolicy = "no-referrer"; cover.append(image); }
      }).catch(() => { if (current === sequence) count.textContent = "Не удалось проверить доступность мест. Откройте маршрут ещё раз."; });
    }
    savedPages.refresh();
  };
  document.addEventListener("kidstime:saved-walks-changed", () => { refreshCounts(); renderRoutes(); });
  window.addEventListener("storage", (event) => {
    if (event.key === storageKey || event.key === null) document.dispatchEvent(new Event("kidstime:saved-walks-changed"));
    if (event.key === "kidstime:favorites") refreshCounts();
  });
  refreshCounts(); renderRoutes();
})();
