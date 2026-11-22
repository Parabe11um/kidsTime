window.KidsTimeReady = (async () => {
  const places = await import(document.body.dataset.pointsModule);
  const personalStore = places.createMapPointStore({
    getItem: key => window.localStorage.getItem(key),
    setItem: (key, value) => window.localStorage.setItem(key, value),
  });
  const favoriteStorageKey = "kidstime:favorites";
  const walkStorageKey = "kidstime:walk";
  const originStorageKey = "kidstime:walk-origin:v1";
  let loadedWalkEvents = [];
  const defaultWalkLimit = 9;

  const readFavorites = () => {
    try {
      const values = JSON.parse(window.localStorage.getItem(favoriteStorageKey) || "[]");
      return new Set((Array.isArray(values) ? values : []).map(String).filter((id) => /^\d{1,19}$/.test(id)).slice(0, 100));
    } catch (_error) {
      return new Set();
    }
  };

  const writeFavorites = (favorites) => {
    try {
      window.localStorage.setItem(favoriteStorageKey, JSON.stringify(Array.from(favorites)));
    } catch (_error) {
      showWalkNotice("Браузер не разрешает сохранение. Подборка доступна только до закрытия страницы.");
    }
  };

  const refreshFavoriteButton = (button, favorites) => {
    const selected = favorites.has(String(button.dataset.favoriteButton));
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    if (!button.querySelector(".ui-icon")) button.textContent = selected ? "♥" : "♡";
  };

  const accountRoot = document.querySelector("[data-account-favorites]");
  const accountMode = Boolean(accountRoot);
  const favorites = accountMode
    ? new Set(JSON.parse(document.getElementById("account-favorites").textContent).map(String))
    : readFavorites();
  const setFavorites = (ids) => {
    favorites.clear();
    ids.forEach((id) => favorites.add(String(id)));
    document.querySelectorAll("[data-favorite-button]").forEach((button) => refreshFavoriteButton(button, favorites));
    document.dispatchEvent(new CustomEvent("kidstime:favorites-changed", { detail: { count: favorites.size } }));
  };
  const saveAccountFavorites = async (url, payload) => {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": accountRoot.querySelector("[name=csrfmiddlewaretoken]").value },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error("favorite save failed");
    const data = await response.json();
    setFavorites(data.ids);
  };
  const favoritesReady = (async () => {
    const guestIds = Array.from(readFavorites());
    if (!accountMode || !guestIds.length) return;
    try {
      await saveAccountFavorites(accountRoot.dataset.mergeUrl, { ids: guestIds });
      window.localStorage.removeItem(favoriteStorageKey);
    } catch (_error) {
      showWalkNotice("Не удалось перенести избранное из браузера. Попробуйте обновить страницу.");
    }
  })();
  let favoriteBusy = false;
  const bindFavoriteButtons = (scope = document) => {
    scope.querySelectorAll("[data-favorite-button]:not([data-favorite-bound])").forEach((button) => {
      button.dataset.favoriteBound = "true";
      refreshFavoriteButton(button, favorites);
      button.addEventListener("click", async () => {
        await favoritesReady;
        if (favoriteBusy) return;
        const id = String(button.dataset.favoriteButton);
        const selected = !favorites.has(id);
        if (selected && favorites.size >= 100) {
          showWalkNotice("Можно сохранить до 100 событий. Удалите одно из избранного.");
          return;
        }
        if (accountMode) {
          favoriteBusy = true;
          button.disabled = true;
          try {
            await saveAccountFavorites(accountRoot.dataset.saveUrl.replace("/0/", `/${id}/`), { favorite: selected });
          } catch (_error) {
            showWalkNotice("Не удалось сохранить избранное. Обновите страницу и попробуйте ещё раз.");
          } finally {
            favoriteBusy = false;
            button.disabled = false;
          }
        } else {
          selected ? favorites.add(id) : favorites.delete(id);
          writeFavorites(favorites);
          setFavorites(Array.from(favorites));
        }
      });
    });
  };
  bindFavoriteButtons();

  const favoriteContainer = document.querySelector("[data-device-favorites]");
  const favoritePage = favoriteContainer?.closest(".favorites-page");
  const filterFavorites = () => {
    if (!favoriteContainer) return;
    favoriteContainer.querySelectorAll("[data-event-id]").forEach((card) => {
      card.hidden = !favorites.has(card.dataset.eventId);
      card.dataset.favoriteMatch = String(!card.hidden);
    });
    favoritePage?.classList.toggle("is-empty", Boolean(favoriteContainer.querySelector(".favorites-empty")));
    document.dispatchEvent(new Event("kidstime:favorite-cards-filtered"));
  };
  let favoriteLoadSequence = 0;
  const loadFavoriteCards = async () => {
    if (!favoriteContainer) return;
    const sequence = ++favoriteLoadSequence;
    await favoritesReady;
    if (sequence !== favoriteLoadSequence) return;
    const emptyTemplate = document.querySelector("[data-favorites-empty]");
    if (!favorites.size) {
      favoriteContainer.innerHTML = emptyTemplate?.innerHTML || "";
      filterFavorites();
      return;
    }
    try {
      const ids = Array.from(favorites).join(",");
      const response = await fetch(`${favoriteContainer.dataset.endpoint}?ids=${encodeURIComponent(ids)}`, { headers: { Accept: "text/html" } });
      if (!response.ok) throw new Error("favorites unavailable");
      const html = await response.text();
      if (sequence !== favoriteLoadSequence) return;
      favoriteContainer.innerHTML = html.trim() || emptyTemplate?.innerHTML || "";
      bindFavoriteButtons(favoriteContainer);
      filterFavorites();
    } catch (_error) {
      if (sequence !== favoriteLoadSequence) return;
      favoriteContainer.innerHTML = '<div class="empty-state">Не удалось загрузить избранное. Обновите страницу.</div>';
      favoritePage?.classList.remove("is-empty");
      document.dispatchEvent(new Event("kidstime:favorite-cards-filtered"));
    }
  };
  loadFavoriteCards();
  document.addEventListener("kidstime:favorites-changed", loadFavoriteCards);

  const walkRoot = document.querySelector("[data-walk-root]");
  const configuredWalkLimit = Number.parseInt(walkRoot?.dataset.limit || "", 10);
  const walkLimit = Number.isInteger(configuredWalkLimit) && configuredWalkLimit > 0
    ? configuredWalkLimit
    : defaultWalkLimit;

  const normalizeWalkIds = values => places.normalizeWalkRefs(values, walkLimit);

  const readWalkIds = () => {
    try {
      return normalizeWalkIds(JSON.parse(window.localStorage.getItem(walkStorageKey) || "[]"));
    } catch (_error) {
      return [];
    }
  };

  let walkIds = readWalkIds();
  let noticeTimer;
  const readOriginRef = () => {
    try { const ref = localStorage.getItem(originStorageKey); return places.personalPointId(ref) ? ref : null; }
    catch (_) { return null; }
  };
  let originRef = readOriginRef(), transientOrigin = null;
  const getPersonalPoints = () => personalStore.list();
  const getOrigin = () => {
    if (!originRef) return transientOrigin ? { ...transientOrigin } : null;
    try { return places.resolvePersonalOrigin(originRef, getPersonalPoints()); }
    catch (_) { return null; }
  };
  const writeOriginRef = ref => {
    try {
      if (ref) localStorage.setItem(originStorageKey, ref); else localStorage.removeItem(originStorageKey);
      return true;
    } catch (_) { showWalkNotice("Не удалось сохранить начальную точку. Разрешите хранение данных сайта в браузере."); return false; }
  };
  let observedOrigin = getOrigin();
  const originChanged = () => {
    const point = getOrigin();
    const coordinatesChanged = observedOrigin?.lat !== point?.lat || observedOrigin?.lng !== point?.lng;
    observedOrigin = point;
    refreshWalkControls();
    document.dispatchEvent(new CustomEvent("kidstime:walk-origin-changed", { detail: { coordinatesChanged } }));
  };
  const setOrigin = point => {
    const ref = point?.source === "personal" ? places.personalPointRef(point.pointId) : null;
    if (ref) {
      try { if (!places.resolvePersonalOrigin(ref, getPersonalPoints())) { showWalkNotice("Личная точка уже удалена. Выберите другую."); return false; } }
      catch (_) { showWalkNotice("Не удалось открыть личные точки. Проверьте настройки браузера."); return false; }
    } else if (point && !places.validCoordinates(point)) return false;
    if ((ref || originRef) && !writeOriginRef(ref)) return false;
    originRef = ref; transientOrigin = ref ? null : point ? { ...point } : null;
    if (ref && walkIds.includes(ref)) replaceWalkIds(walkIds.filter(id => id !== ref));
    originChanged();
    return true;
  };

  const writeWalkIds = () => {
    try {
      window.localStorage.setItem(walkStorageKey, JSON.stringify(walkIds));
    } catch (_error) {
      showWalkNotice("Браузер не разрешает сохранение. Прогулка доступна только до закрытия страницы.");
    }
  };

  const showWalkNotice = (message) => {
    let notice = document.querySelector("[data-walk-notice]");
    if (!notice) {
      notice = document.createElement("div");
      notice.className = "walk-notice";
      notice.dataset.walkNotice = "true";
      notice.setAttribute("role", "status");
      notice.setAttribute("aria-live", "polite");
      document.body.append(notice);
    }
    notice.textContent = message;
    notice.classList.add("is-visible");
    window.clearTimeout(noticeTimer);
    noticeTimer = window.setTimeout(() => notice.classList.remove("is-visible"), 2600);
  };

  const refreshWalkButton = (button) => {
    const id = String(button.dataset.walkButton || "");
    if (!id) return;
    const selected = walkIds.includes(id);
    const defaultLabel = button.dataset.walkDefaultLabel || "+ В прогулку";
    const activeLabel = button.dataset.walkActiveLabel || "✓ В прогулке";
    const isOrigin = places.personalPointId(id) && id === originRef;
    button.disabled = Boolean(isOrigin);
    button.classList.toggle("is-active", selected || isOrigin);
    button.setAttribute("aria-pressed", selected || isOrigin ? "true" : "false");
    button.textContent = isOrigin ? "Начальная точка" : selected ? activeLabel : defaultLabel;
  };

  const refreshWalkControls = () => {
    document.querySelectorAll("[data-walk-button]").forEach(refreshWalkButton);
    document.querySelectorAll("[data-walk-count]").forEach((counter) => {
      counter.textContent = String(walkIds.length);
      counter.hidden = walkIds.length === 0 && !counter.hasAttribute("data-walk-count-always");
    });
  };

  const replaceWalkIds = (values, { announce = false } = {}) => {
    walkIds = normalizeWalkIds(values).filter(id => id !== originRef);
    writeWalkIds();
    refreshWalkControls();
    document.dispatchEvent(new CustomEvent("kidstime:walk-changed", { detail: { ids: [...walkIds] } }));
    if (announce) showWalkNotice("Прогулка обновлена");
  };

  const toggleWalkPoint = (id) => {
    if (id === originRef) { showWalkNotice("Эта точка уже выбрана началом маршрута"); return; }
    if (walkIds.includes(id)) {
      replaceWalkIds(walkIds.filter((item) => item !== id));
      showWalkNotice("Точка удалена из прогулки");
      return;
    }
    if (walkIds.length >= walkLimit) {
      showWalkNotice(`Можно добавить не более ${walkLimit} точек`);
      return;
    }
    replaceWalkIds([...walkIds, id]);
    showWalkNotice("Точка добавлена в прогулку");
  };

  window.KidsTimeFavorites = { getCount: () => favorites.size };
  window.KidsTimeWalk = {
    getIds: () => [...walkIds],
    getEvents: () => [...loadedWalkEvents],
    replaceIds: replaceWalkIds,
    notice: showWalkNotice,
    refreshButton: refreshWalkButton,
    getOrigin, setOrigin, getOriginRef: () => originRef,
    getPersonalPoints, places,
    normalizeIds: normalizeWalkIds,
    isComplete: () => loadedWalkEvents.length > 0 && !walkRoot?.hasAttribute("aria-busy") && (!originRef || Boolean(getOrigin())),
    restore: (ids, ref) => {
      const next = places.personalPointId(ref) ? ref : null;
      if ((next || originRef) && !writeOriginRef(next)) return false;
      originRef = next; transientOrigin = null; replaceWalkIds(ids); originChanged(); return true;
    },
    resolvePoints: async (ids, endpoint) => {
      const refs = normalizeWalkIds(ids), catalogIds = refs.filter(id => !places.personalPointId(id));
      let events = [];
      if (catalogIds.length) {
        const response = await fetch(`${endpoint}?ids=${encodeURIComponent(catalogIds.join(","))}`, { headers: { Accept: "application/json" } });
        if (!response.ok) throw new Error("walk unavailable");
        const payload = await response.json();
        if (!Array.isArray(payload.results)) throw new Error("walk unavailable");
        events = payload.results;
      }
      return places.resolveWalkPoints(refs, events, refs.some(id => places.personalPointId(id)) ? getPersonalPoints() : []);
    },
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-walk-button]");
    if (!button || button.disabled) return;
    const id = String(button.dataset.walkButton || "");
    if (!normalizeWalkIds([id]).length) return;
    toggleWalkPoint(id);
  });

  refreshWalkControls();

  window.addEventListener("storage", (event) => {
    if (!accountMode && (event.key === favoriteStorageKey || event.key === null)) {
      favorites.clear();
      readFavorites().forEach((id) => favorites.add(id));
      document.querySelectorAll("[data-favorite-button]").forEach((button) => refreshFavoriteButton(button, favorites));
      loadFavoriteCards();
    }
    if (event.key === places.MAP_POINTS_KEY || event.key === null) document.dispatchEvent(new Event("kidstime:personal-points-changed"));
    if (event.key === originStorageKey || event.key === null) { originRef = readOriginRef(); transientOrigin = null; originChanged(); }
    if (event.key !== walkStorageKey && event.key !== null) return;
    walkIds = readWalkIds();
    refreshWalkControls();
    document.dispatchEvent(new CustomEvent("kidstime:walk-changed", { detail: { ids: [...walkIds] } }));
  });

  document.addEventListener("kidstime:personal-points-changed", () => {
    originChanged();
    try {
      const available = new Set(getPersonalPoints().map(point => places.personalPointRef(point.id)));
      const ids = walkIds.filter(id => !places.personalPointId(id) || available.has(id));
      if (ids.length !== walkIds.length) { replaceWalkIds(ids); return; }
    } catch (_) { /* Keep the selection when browser storage cannot be read. */ }
    if (walkRoot) window.KidsTimeWalk.reload?.();
  });

  if (walkRoot) {
    const list = walkRoot.querySelector("[data-walk-list]");
    const emptyTemplate = walkRoot.querySelector("[data-walk-empty]");
    const routeLink = walkRoot.querySelector("[data-walk-route]");
    const clearButton = walkRoot.querySelector("[data-walk-clear]");
    let loadSequence = 0;
    const directRouteUrl = (event) => (
      `https://yandex.ru/maps/?rtext=~${encodeURIComponent(`${event.lat},${event.lng}`)}&rtt=pd`
    );

    const walkRouteUrl = (events) => {
      const points = events.map((event) => encodeURIComponent(`${event.lat},${event.lng}`));
      const origin = getOrigin();
      const start = origin ? `${origin.lat},${origin.lng}` : "";
      return `https://yandex.ru/maps/?rtext=${encodeURIComponent(start)}~${points.join("~")}&rtt=pd`;
    };

    const makeButton = (label, className, ariaLabel) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.setAttribute("aria-label", ariaLabel);
      return button;
    };

    const createWalkItem = (event, index, events) => {
      const item = document.createElement("article");
      item.className = event.kind === "personal" ? "walk-item walk-item--personal" : "walk-item";
      item.dataset.walkEventId = String(event.id);

      const media = document.createElement("div");
      media.className = "walk-item__media";
      if (event.cover) {
        const image = document.createElement("img");
        image.src = event.cover;
        image.alt = "";
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";
        media.append(image);
      } else {
        const placeholder = document.createElement("span");
        placeholder.className = "walk-item__image-empty";
        placeholder.setAttribute("aria-hidden", "true");
        media.append(placeholder);
      }
      const number = document.createElement("span");
      number.className = "walk-item__number";
      number.textContent = String(index + 2);

      const content = document.createElement("div");
      content.className = "walk-item__content";
      const title = document.createElement(event.kind === "personal" ? "span" : "a");
      title.className = "walk-item__title";
      if (event.kind !== "personal") title.href = event.url;
      title.textContent = event.title;
      const venue = document.createElement("strong");
      venue.textContent = event.venue;
      const address = document.createElement("p");
      address.textContent = event.address;
      const facts = document.createElement("div");
      facts.className = "walk-item__facts";
      [[event.date, "calendar"], [event.age, "child"], [event.price, "wallet"]].forEach(([value, iconName]) => {
        if (!value) return;
        const fact = document.createElement("span");
        if (iconName === "calendar") fact.className = "walk-item__date";
        const icon = document.createElement("span"); icon.className = `ui-icon ui-icon--${iconName}`; icon.setAttribute("aria-hidden", "true");
        fact.append(icon, document.createTextNode(value));
        facts.append(fact);
      });

      const actions = document.createElement("div");
      actions.className = "walk-item__actions";
      const directRoute = document.createElement("a");
      directRoute.className = "walk-item__route";
      directRoute.href = directRouteUrl(event);
      directRoute.target = "_blank";
      directRoute.rel = "noopener";
      directRoute.textContent = "Маршрут сюда";

      const reorder = document.createElement("div");
      reorder.className = "walk-item__reorder";
      const moveUp = makeButton("", "walk-item__move", `Переместить «${event.title}» выше`);
      const upIcon = document.createElement("span");
      upIcon.className = "ui-icon ui-icon--arrow-up";
      upIcon.setAttribute("aria-hidden", "true");
      moveUp.append(upIcon);
      moveUp.dataset.walkMove = "-1";
      moveUp.dataset.eventId = String(event.id);
      moveUp.disabled = index === 0;
      const moveDown = makeButton("", "walk-item__move", `Переместить «${event.title}» ниже`);
      const downIcon = document.createElement("span");
      downIcon.className = "ui-icon ui-icon--arrow-down";
      downIcon.setAttribute("aria-hidden", "true");
      moveDown.append(downIcon);
      moveDown.dataset.walkMove = "1";
      moveDown.dataset.eventId = String(event.id);
      moveDown.disabled = index === events.length - 1;
      const remove = makeButton("", "walk-item__remove", `Удалить «${event.title}» из прогулки`);
      const removeIcon = document.createElement("span");
      removeIcon.className = "ui-icon ui-icon--walk-remove";
      removeIcon.setAttribute("aria-hidden", "true");
      remove.append(removeIcon);
      remove.dataset.walkRemove = String(event.id);
      reorder.append(moveUp, moveDown, remove);
      actions.append(directRoute, reorder);
      content.append(title, venue, address, facts, actions);
      if (event.description) {
        const description = document.createElement("p");
        description.className = "walk-item__description";
        description.textContent = event.description;
        content.insertBefore(description, actions);
      }
      const toolbar = document.createElement("div");
      toolbar.className = "walk-item__toolbar";
      toolbar.append(number, reorder);
      const favorite = makeButton("", "favorite-button", `В избранное: ${event.title}`);
      favorite.dataset.favoriteButton = String(event.id);
      const heart = document.createElement("span");
      heart.className = "ui-icon ui-icon--heart";
      heart.setAttribute("aria-hidden", "true");
      favorite.append(heart);
      if (event.kind !== "personal") media.append(favorite);
      item.append(toolbar, media, content);
      bindFavoriteButtons(item);
      return item;
    };

    const updateRouteLink = (events) => {
      const hasPoints = events.length > 0 && (!originRef || Boolean(getOrigin()));
      routeLink.classList.toggle("is-disabled", !hasPoints);
      routeLink.setAttribute("aria-disabled", hasPoints ? "false" : "true");
      if (hasPoints) {
        routeLink.href = walkRouteUrl(events);
      } else {
        routeLink.removeAttribute("href");
      }
    };

    const renderWalk = (events) => {
      loadedWalkEvents = events;
      walkRoot.classList.toggle("is-empty", !events.length);
      walkRoot.removeAttribute("aria-busy");
      list.replaceChildren();
      clearButton.hidden = events.length === 0;
      updateRouteLink(events);
      if (!events.length) {
        list.append(emptyTemplate.content.cloneNode(true));
        document.dispatchEvent(new CustomEvent("kidstime:walk-loaded", { detail: { events } }));
        return;
      }
      const fragment = document.createDocumentFragment();
      events.forEach((event, index) => fragment.append(createWalkItem(event, index, events)));
      list.append(fragment);
      document.dispatchEvent(new CustomEvent("kidstime:walk-loaded", { detail: { events } }));
    };

    const renderLoadError = () => {
      list.replaceChildren();
      clearButton.hidden = walkIds.length === 0;
      const error = document.createElement("div");
      error.className = "empty-state";
      const text = document.createElement("p");
      text.textContent = "Не удалось загрузить точки прогулки.";
      const retry = makeButton("Попробовать ещё раз", "secondary-button", "Повторить загрузку прогулки");
      retry.dataset.walkRetry = "true";
      error.append(text, retry);
      list.append(error);
      updateRouteLink([]);
      walkRoot.removeAttribute("aria-busy");
      document.dispatchEvent(new Event("kidstime:walk-load-error"));
    };

    const loadWalk = async () => {
      const sequence = ++loadSequence;
      loadedWalkEvents = [];
      walkRoot.setAttribute("aria-busy", "true");
      updateRouteLink([]);
      document.dispatchEvent(new Event("kidstime:walk-loading"));
      if (!walkIds.length) {
        renderWalk([]);
        return;
      }
      try {
        const events = await window.KidsTimeWalk.resolvePoints(walkIds, walkRoot.dataset.endpoint);
        if (sequence !== loadSequence) return;
        const validIds = events.map((event) => String(event.id));
        if (validIds.join(",") !== walkIds.join(",")) {
          walkIds = normalizeWalkIds(validIds);
          writeWalkIds();
          refreshWalkControls();
          showWalkNotice("Недоступные точки убраны из текущего маршрута.");
        }
        renderWalk(events);
      } catch (_error) {
        if (sequence === loadSequence) renderLoadError();
      }
    };

    walkRoot.addEventListener("click", (event) => {
      const removeButton = event.target.closest("[data-walk-remove]");
      if (removeButton) {
        replaceWalkIds(walkIds.filter((id) => id !== removeButton.dataset.walkRemove));
        showWalkNotice("Точка удалена из прогулки");
        return;
      }

      const moveButton = event.target.closest("[data-walk-move]");
      if (moveButton && !moveButton.disabled) {
        const currentIndex = walkIds.indexOf(moveButton.dataset.eventId);
        const nextIndex = currentIndex + Number(moveButton.dataset.walkMove);
        if (currentIndex >= 0 && nextIndex >= 0 && nextIndex < walkIds.length) {
          const reordered = [...walkIds];
          [reordered[currentIndex], reordered[nextIndex]] = [reordered[nextIndex], reordered[currentIndex]];
          replaceWalkIds(reordered);
        }
        return;
      }

      if (event.target.closest("[data-walk-clear]")) {
        replaceWalkIds([]);
        window.KidsTimeWalk.setOrigin(null);
        showWalkNotice("Прогулка очищена");
        return;
      }

      if (event.target.closest("[data-walk-retry]")) loadWalk();
    });

    window.KidsTimeWalk.reload = loadWalk;
    document.addEventListener("kidstime:walk-changed", loadWalk);
    document.addEventListener("kidstime:walk-origin-changed", () => updateRouteLink(loadedWalkEvents));
    loadWalk();
  }

  const filtersPanel = document.getElementById("filters-panel");
  const backdrop = document.querySelector(".filters-backdrop");
  const desktopViewport = window.matchMedia("(min-width: 1024px)");
  let filtersReturnFocus;
  const setFiltersOpen = (open) => {
    if (!filtersPanel || !backdrop) return;
    if (desktopViewport.matches) {
      if (open) filtersPanel.querySelector('input:not([type="hidden"])')?.focus();
      return;
    }
    if (open) filtersReturnFocus = document.activeElement;
    filtersPanel.classList.toggle("is-open", open);
    backdrop.classList.toggle("is-open", open);
    document.body.classList.toggle("has-overlay", open);
    if (open) {
      filtersPanel.setAttribute("role", "dialog");
      filtersPanel.setAttribute("aria-modal", "true");
      filtersPanel.querySelector("[data-filters-close]")?.focus();
    } else {
      filtersPanel.removeAttribute("role");
      filtersPanel.removeAttribute("aria-modal");
      filtersReturnFocus?.focus();
    }
    document.querySelectorAll('[data-filters-open], .search-filter-button[name="filters"]').forEach((button) => button.setAttribute("aria-expanded", String(open)));
  };

  document.querySelectorAll("[data-filters-open]").forEach((button) => {
    button.addEventListener("click", () => setFiltersOpen(true));
  });
  document.querySelectorAll("[data-filters-close]").forEach((button) => {
    button.addEventListener("click", () => setFiltersOpen(false));
  });
  document.addEventListener("keydown", (event) => {
    if (!filtersPanel?.classList.contains("is-open")) return;
    if (event.key === "Escape") setFiltersOpen(false);
    if (event.key !== "Tab") return;
    const items = [...filtersPanel.querySelectorAll('a[href],button:not(:disabled),input:not([type="hidden"]),select')].filter((item) => item.getClientRects().length);
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault(); last?.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault(); first?.focus();
    }
  });
  desktopViewport.addEventListener("change", () => {
    filtersPanel?.classList.remove("is-open");
    filtersPanel?.removeAttribute("role");
    filtersPanel?.removeAttribute("aria-modal");
    backdrop?.classList.remove("is-open");
    document.body.classList.remove("has-overlay");
    document.querySelectorAll('[data-filters-open], .search-filter-button[name="filters"]').forEach((button) => button.setAttribute("aria-expanded", "false"));
  });
  if (new URLSearchParams(window.location.search).get("filters") === "open") setFiltersOpen(true);

  // On the results page the search button opens the existing sheet without a reload.
  if (filtersPanel) {
    document.querySelectorAll('.search-filter-button[name="filters"]').forEach((button) => {
      button.setAttribute("aria-controls", "filters-panel");
      button.setAttribute("aria-expanded", String(filtersPanel.classList.contains("is-open")));
      button.addEventListener("click", (event) => {
        event.preventDefault();
        const query = button.form.querySelector('[name="q"]')?.value;
        if (query !== undefined) filtersPanel.querySelector('[name="q"]').value = query;
        setFiltersOpen(true);
      });
    });
  }

  document.querySelector("[data-filter-location]")?.addEventListener("click", (event) => {
    const button = event.currentTarget;
    const status = document.querySelector("[data-location-status]");
    if (!navigator.geolocation) {
      status.textContent = "Браузер не поддерживает определение местоположения.";
      return;
    }
    button.disabled = true;
    status.textContent = "Определяем местоположение…";
    navigator.geolocation.getCurrentPosition((position) => {
      filtersPanel.querySelector('[name="lat"]').value = position.coords.latitude;
      filtersPanel.querySelector('[name="lng"]').value = position.coords.longitude;
      status.textContent = "Местоположение выбрано";
      button.disabled = false;
    }, () => {
      status.textContent = "Не удалось определить местоположение. Проверьте разрешение браузера.";
      button.disabled = false;
    }, { maximumAge: 300000, timeout: 10000 });
  });

  const scrollBehavior = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";
  document.querySelectorAll("[data-feed-tabs]").forEach((feed) => {
    const tabs = [...feed.querySelectorAll('[role="tab"]')];
    const panels = [...feed.querySelectorAll('[role="tabpanel"]')];
    const selectTab = (selected) => {
      tabs.forEach((tab) => {
        const active = tab === selected;
        tab.setAttribute("aria-selected", String(active));
        tab.tabIndex = active ? 0 : -1;
        tab.classList.toggle("is-active", active);
      });
      panels.forEach((panel) => { panel.hidden = panel.id !== selected.getAttribute("aria-controls"); });
    };
    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => selectTab(tab));
      tab.addEventListener("keydown", (event) => {
        const next = { ArrowRight: (index + 1) % tabs.length, ArrowLeft: (index - 1 + tabs.length) % tabs.length, Home: 0, End: tabs.length - 1 }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        selectTab(tabs[next]);
        tabs[next].focus();
      });
    });
  });
  document.querySelectorAll("[data-carousel]").forEach((carousel) => {
    const track = carousel.querySelector("[data-carousel-track]");
    const cards = [...track.querySelectorAll(".spotlight-card")];
    const pauseButton = carousel.querySelector("[data-carousel-pause]");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let activeIndex = 0;
    let paused = reducedMotion.matches;
    let inView = false;
    let timer;
    const syncPlayback = () => {
      window.clearTimeout(timer);
      if (pauseButton) {
        pauseButton.setAttribute("aria-pressed", String(paused));
        pauseButton.textContent = paused ? "Продолжить показ" : "Приостановить показ";
      }
      if (cards.length < 2 || paused || !inView || !desktopViewport.matches || document.hidden || carousel.matches(":hover") || carousel.contains(document.activeElement)) return;
      timer = window.setTimeout(() => move(1), 7000);
    };
    const render = (animate = false, direction = 1) => {
      const before = new Map(cards.filter((card) => card.getClientRects().length).map((card) => [card, card.getBoundingClientRect()]));
      cards.forEach((card, index) => {
        card.getAnimations().forEach((animation) => animation.cancel());
        const active = index === activeIndex;
        const previous = cards.length > 2 && index === (activeIndex - 1 + cards.length) % cards.length;
        const next = cards.length > 1 && index === (activeIndex + 1) % cards.length;
        card.classList.toggle("is-active", active);
        card.classList.toggle("is-prev", previous);
        card.classList.toggle("is-next", next);
        card.setAttribute("aria-hidden", String(!active && !previous && !next));
      });
      if (animate && !reducedMotion.matches) {
        cards.filter((card) => card.getClientRects().length).forEach((card) => {
          const target = card.getBoundingClientRect();
          const from = before.get(card);
          const x = from ? from.x - target.x : direction * 120;
          const y = from ? from.y - target.y : 0;
          const scaleX = from && target.width ? from.width / target.width : .94;
          const scaleY = from && target.height ? from.height / target.height : .94;
          card.animate([
            { transformOrigin: "top left", transform: `translate(${x}px,${y}px) scale(${scaleX},${scaleY})`, opacity: from ? 1 : 0 },
            { transformOrigin: "top left", transform: "translate(0,0) scale(1)", opacity: 1 },
          ], { duration: 650, easing: "cubic-bezier(.22,.61,.36,1)" });
        });
      }
      syncPlayback();
    };
    const move = (direction) => {
      if (!cards.length) return;
      activeIndex = (activeIndex + direction + cards.length) % cards.length;
      render(true, direction);
    };
    carousel.querySelector("[data-carousel-prev]")?.addEventListener("click", () => move(-1));
    carousel.querySelector("[data-carousel-next]")?.addEventListener("click", () => move(1));
    carousel.querySelectorAll("[data-carousel-select]").forEach((button) => {
      button.addEventListener("click", () => {
        const direction = button.closest(".spotlight-card").classList.contains("is-prev") ? -1 : 1;
        activeIndex = Number(button.dataset.carouselSelect);
        render(true, direction);
        track.focus({ preventScroll: true });
      });
    });
    track.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault(); move(event.key === "ArrowRight" ? 1 : -1);
      track.focus({ preventScroll: true });
    });
    pauseButton?.addEventListener("click", () => { paused = !paused; syncPlayback(); });
    carousel.addEventListener("pointerenter", syncPlayback);
    carousel.addEventListener("pointerleave", syncPlayback);
    carousel.addEventListener("focusin", syncPlayback);
    carousel.addEventListener("focusout", () => window.setTimeout(syncPlayback, 0));
    document.addEventListener("visibilitychange", syncPlayback);
    desktopViewport.addEventListener("change", syncPlayback);
    reducedMotion.addEventListener("change", () => { paused = reducedMotion.matches; syncPlayback(); });
    new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; syncPlayback(); }, { threshold: .3 }).observe(carousel);
    render();
  });

  document.querySelectorAll("[data-gallery]").forEach((gallery) => {
    const track = gallery.querySelector("[data-gallery-track]");
    const buttons = [...gallery.querySelectorAll("[data-gallery-index]")];
    const goTo = (index) => track.scrollTo({ left: index * track.clientWidth, behavior: scrollBehavior() });
    buttons.forEach((button) => button.addEventListener("click", () => goTo(Number(button.dataset.galleryIndex))));
    track.addEventListener("scroll", () => {
      const index = Math.round(track.scrollLeft / track.clientWidth);
      buttons.forEach((button) => button.setAttribute("aria-pressed", String(Number(button.dataset.galleryIndex) === index)));
    }, { passive: true });
    track.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault();
      goTo(Math.max(0, Math.min(track.children.length - 1, Math.round(track.scrollLeft / track.clientWidth) + (event.key === "ArrowRight" ? 1 : -1))));
    });
  });

  document.querySelectorAll("[data-share]").forEach(button => button.addEventListener("click", async () => {
    try {
      if (navigator.share) await navigator.share({ title: document.title, url: window.location.href });
      else {
        await navigator.clipboard.writeText(window.location.href);
        showWalkNotice("Ссылка скопирована");
      }
    } catch (error) {
      if (error.name !== "AbortError") showWalkNotice("Не удалось поделиться. Скопируйте адрес из строки браузера.");
    }
  }));
})();
