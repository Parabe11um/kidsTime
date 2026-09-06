(() => {
  const favoriteStorageKey = "kidstime:favorites";
  const walkStorageKey = "kidstime:walk";
  const defaultWalkLimit = 9;

  const readFavorites = () => {
    try {
      return new Set(JSON.parse(window.localStorage.getItem(favoriteStorageKey) || "[]").map(String));
    } catch (_error) {
      return new Set();
    }
  };

  const writeFavorites = (favorites) => {
    window.localStorage.setItem(favoriteStorageKey, JSON.stringify(Array.from(favorites)));
  };

  const refreshFavoriteButton = (button, favorites) => {
    const selected = favorites.has(String(button.dataset.favoriteButton));
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.textContent = selected ? "♥" : "♡";
  };

  const favorites = readFavorites();
  const bindFavoriteButtons = (scope = document) => {
    scope.querySelectorAll("[data-favorite-button]:not([data-favorite-bound])").forEach((button) => {
      button.dataset.favoriteBound = "true";
      refreshFavoriteButton(button, favorites);
      button.addEventListener("click", () => {
        const id = String(button.dataset.favoriteButton);
        if (favorites.has(id)) {
          favorites.delete(id);
        } else {
          favorites.add(id);
        }
        writeFavorites(favorites);
        document.querySelectorAll(`[data-favorite-button="${id}"]`).forEach((item) => {
          refreshFavoriteButton(item, favorites);
        });
      });
    });
  };
  bindFavoriteButtons();

  const favoriteContainer = document.querySelector("[data-device-favorites]");
  if (favoriteContainer) {
    const emptyTemplate = document.querySelector("[data-favorites-empty]");
    if (!favorites.size) {
      favoriteContainer.innerHTML = emptyTemplate?.innerHTML || "";
    } else {
      const ids = Array.from(favorites).join(",");
      fetch(`${favoriteContainer.dataset.endpoint}?ids=${encodeURIComponent(ids)}`, {
        headers: { Accept: "text/html" },
      })
        .then((response) => {
          if (!response.ok) throw new Error("favorites unavailable");
          return response.text();
        })
        .then((html) => {
          favoriteContainer.innerHTML = html.trim() || emptyTemplate?.innerHTML || "";
          bindFavoriteButtons(favoriteContainer);
        })
        .catch(() => {
          favoriteContainer.innerHTML = '<div class="empty-state">Не удалось загрузить избранное. Обновите страницу.</div>';
        });
    }
  }

  const walkRoot = document.querySelector("[data-walk-root]");
  const configuredWalkLimit = Number.parseInt(walkRoot?.dataset.limit || "", 10);
  const walkLimit = Number.isInteger(configuredWalkLimit) && configuredWalkLimit > 0
    ? configuredWalkLimit
    : defaultWalkLimit;

  const normalizeWalkIds = (values) => {
    const normalized = [];
    for (const value of Array.isArray(values) ? values : []) {
      const id = String(value).trim();
      if (!/^\d+$/.test(id) || normalized.includes(id)) continue;
      normalized.push(id);
      if (normalized.length === walkLimit) break;
    }
    return normalized;
  };

  const readWalkIds = () => {
    try {
      return normalizeWalkIds(JSON.parse(window.localStorage.getItem(walkStorageKey) || "[]"));
    } catch (_error) {
      return [];
    }
  };

  let walkIds = readWalkIds();
  let noticeTimer;

  const writeWalkIds = () => {
    window.localStorage.setItem(walkStorageKey, JSON.stringify(walkIds));
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
    button.classList.toggle("is-active", selected);
    button.setAttribute("aria-pressed", selected ? "true" : "false");
    button.textContent = selected ? activeLabel : defaultLabel;
  };

  const refreshWalkControls = () => {
    document.querySelectorAll("[data-walk-button]").forEach(refreshWalkButton);
    document.querySelectorAll("[data-walk-count]").forEach((counter) => {
      counter.textContent = String(walkIds.length);
      counter.hidden = walkIds.length === 0 && !counter.hasAttribute("data-walk-count-always");
    });
  };

  const replaceWalkIds = (values, { announce = false } = {}) => {
    walkIds = normalizeWalkIds(values);
    writeWalkIds();
    refreshWalkControls();
    document.dispatchEvent(new CustomEvent("kidstime:walk-changed", { detail: { ids: [...walkIds] } }));
    if (announce) showWalkNotice("Прогулка обновлена");
  };

  const toggleWalkPoint = (id) => {
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

  window.KidsTimeWalk = {
    getIds: () => [...walkIds],
    refreshButton: refreshWalkButton,
  };

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-walk-button]");
    if (!button || button.disabled) return;
    const id = String(button.dataset.walkButton || "");
    if (!/^\d+$/.test(id)) return;
    toggleWalkPoint(id);
  });

  refreshWalkControls();

  window.addEventListener("storage", (event) => {
    if (event.key !== walkStorageKey) return;
    walkIds = readWalkIds();
    refreshWalkControls();
    document.dispatchEvent(new CustomEvent("kidstime:walk-changed", { detail: { ids: [...walkIds] } }));
  });

  if (walkRoot) {
    const list = walkRoot.querySelector("[data-walk-list]");
    const emptyTemplate = walkRoot.querySelector("[data-walk-empty]");
    const routeLink = walkRoot.querySelector("[data-walk-route]");
    const clearButton = walkRoot.querySelector("[data-walk-clear]");
    let loadSequence = 0;

    const directRouteUrl = (event) => (
      `https://yandex.ru/maps/?rtext=~${encodeURIComponent(`${event.lat},${event.lng}`)}&rtt=auto`
    );

    const walkRouteUrl = (events) => {
      const points = events.map((event) => encodeURIComponent(`${event.lat},${event.lng}`));
      return `https://yandex.ru/maps/?rtext=~${points.join("~")}&rtt=auto`;
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
      item.className = "walk-item";

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
      number.textContent = String(index + 1);
      media.append(number);

      const content = document.createElement("div");
      content.className = "walk-item__content";
      const title = document.createElement("a");
      title.className = "walk-item__title";
      title.href = event.url;
      title.textContent = event.title;
      const venue = document.createElement("strong");
      venue.textContent = event.venue;
      const address = document.createElement("p");
      address.textContent = event.address;

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
      const moveUp = makeButton("↑", "walk-item__move", `Переместить «${event.title}» выше`);
      moveUp.dataset.walkMove = "-1";
      moveUp.dataset.eventId = String(event.id);
      moveUp.disabled = index === 0;
      const moveDown = makeButton("↓", "walk-item__move", `Переместить «${event.title}» ниже`);
      moveDown.dataset.walkMove = "1";
      moveDown.dataset.eventId = String(event.id);
      moveDown.disabled = index === events.length - 1;
      const remove = makeButton("Удалить", "walk-item__remove", `Удалить «${event.title}» из прогулки`);
      remove.dataset.walkRemove = String(event.id);
      reorder.append(moveUp, moveDown, remove);
      actions.append(directRoute, reorder);
      content.append(title, venue, address, actions);
      item.append(media, content);
      return item;
    };

    const updateRouteLink = (events) => {
      const hasPoints = events.length > 0;
      routeLink.classList.toggle("is-disabled", !hasPoints);
      routeLink.setAttribute("aria-disabled", hasPoints ? "false" : "true");
      if (hasPoints) {
        routeLink.href = walkRouteUrl(events);
      } else {
        routeLink.removeAttribute("href");
      }
    };

    const renderWalk = (events) => {
      list.replaceChildren();
      clearButton.hidden = events.length === 0;
      updateRouteLink(events);
      if (!events.length) {
        list.append(emptyTemplate.content.cloneNode(true));
        return;
      }
      const fragment = document.createDocumentFragment();
      events.forEach((event, index) => fragment.append(createWalkItem(event, index, events)));
      list.append(fragment);
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
    };

    const loadWalk = async () => {
      const sequence = ++loadSequence;
      if (!walkIds.length) {
        renderWalk([]);
        return;
      }
      try {
        const ids = encodeURIComponent(walkIds.join(","));
        const response = await fetch(`${walkRoot.dataset.endpoint}?ids=${ids}`, {
          headers: { Accept: "application/json" },
        });
        if (!response.ok) throw new Error("walk unavailable");
        const payload = await response.json();
        if (sequence !== loadSequence) return;
        const events = Array.isArray(payload.results) ? payload.results : [];
        const validIds = events.map((event) => String(event.id));
        if (validIds.join(",") !== walkIds.join(",")) {
          walkIds = normalizeWalkIds(validIds);
          writeWalkIds();
          refreshWalkControls();
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
        showWalkNotice("Прогулка очищена");
        return;
      }

      if (event.target.closest("[data-walk-retry]")) loadWalk();
    });

    document.addEventListener("kidstime:walk-changed", loadWalk);
    loadWalk();
  }

  const filtersPanel = document.getElementById("filters-panel");
  const backdrop = document.querySelector(".filters-backdrop");
  const setFiltersOpen = (open) => {
    if (!filtersPanel || !backdrop) return;
    filtersPanel.classList.toggle("is-open", open);
    backdrop.classList.toggle("is-open", open);
    document.body.classList.toggle("has-overlay", open);
  };

  document.querySelectorAll("[data-filters-open]").forEach((button) => {
    button.addEventListener("click", () => setFiltersOpen(true));
  });
  document.querySelectorAll("[data-filters-close]").forEach((button) => {
    button.addEventListener("click", () => setFiltersOpen(false));
  });
})();
