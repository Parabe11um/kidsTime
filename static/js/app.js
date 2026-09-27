(() => {
  const favoriteStorageKey = "kidstime:favorites";
  const walkStorageKey = "kidstime:walk";
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
          if (favorites.size >= 100) {
            showWalkNotice("Можно сохранить до 100 событий. Удалите одно из избранного.");
            return;
          }
          favorites.add(id);
        }
        writeFavorites(favorites);
        document.querySelectorAll(`[data-favorite-button="${id}"]`).forEach((item) => {
          refreshFavoriteButton(item, favorites);
        });
        document.dispatchEvent(new CustomEvent("kidstime:favorites-changed"));
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
          filterFavorites();
        })
        .catch(() => {
          favoriteContainer.innerHTML = '<div class="empty-state">Не удалось загрузить избранное. Обновите страницу.</div>';
        });
    }
  }

  const favoriteSearch = document.querySelector("[data-favorites-search]");
  const filterFavorites = () => {
    if (!favoriteContainer) return;
    const query = (favoriteSearch?.querySelector("input")?.value || "").trim().toLocaleLowerCase("ru");
    let visible = 0;
    favoriteContainer.querySelectorAll("[data-event-id]").forEach((card) => {
      card.hidden = !favorites.has(card.dataset.eventId) || !card.textContent.toLocaleLowerCase("ru").includes(query);
      if (!card.hidden) visible += 1;
    });
    const noResults = document.querySelector("[data-favorites-no-results]");
    if (noResults) noResults.hidden = !query || visible > 0;
  };
  favoriteSearch?.addEventListener("submit", (event) => { event.preventDefault(); filterFavorites(); });
  favoriteSearch?.querySelector("input")?.addEventListener("input", filterFavorites);
  document.addEventListener("kidstime:favorites-changed", filterFavorites);

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
    if (event.key === favoriteStorageKey || event.key === null) {
      favorites.clear();
      readFavorites().forEach((id) => favorites.add(id));
      document.querySelectorAll("[data-favorite-button]").forEach((button) => refreshFavoriteButton(button, favorites));
      filterFavorites();
    }
    if (event.key !== walkStorageKey && event.key !== null) return;
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
      number.textContent = String(index + 2);
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
      const facts = document.createElement("div");
      facts.className = "walk-item__facts";
      [event.date, event.age, event.price].filter(Boolean).forEach((value) => {
        const fact = document.createElement("span");
        fact.textContent = value;
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
      const remove = makeButton("Удалить", "walk-item__remove", `Удалить «${event.title}» из прогулки`);
      remove.dataset.walkRemove = String(event.id);
      reorder.append(moveUp, moveDown, remove);
      actions.append(directRoute, reorder);
      content.append(title, venue, address, facts, actions);
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
  const desktopViewport = window.matchMedia("(min-width: 1024px)");
  let filtersReturnFocus;
  const setFiltersOpen = (open) => {
    if (!filtersPanel || !backdrop) return;
    if (desktopViewport.matches) {
      if (open) filtersPanel.querySelector("input")?.focus();
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
    document.querySelectorAll("[data-filters-open]").forEach((button) => button.setAttribute("aria-expanded", String(open)));
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
    document.querySelectorAll("[data-filters-open]").forEach((button) => button.setAttribute("aria-expanded", "false"));
  });
  if (new URLSearchParams(window.location.search).get("filters") === "open") setFiltersOpen(true);

  // On the results page the search button opens the existing sheet without a reload.
  if (filtersPanel) {
    document.querySelectorAll('.search-filter-button[name="filters"]').forEach((button) => {
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
  document.querySelectorAll("[data-carousel]").forEach((carousel) => {
    const track = carousel.querySelector("[data-carousel-track]");
    const move = (direction) => {
      const cards = [...track.children];
      if (!cards.length) return;
      const start = cards[0].offsetLeft;
      const closest = cards.reduce((best, card, index) => (
        Math.abs(card.offsetLeft - start - track.scrollLeft) < Math.abs(cards[best].offsetLeft - start - track.scrollLeft) ? index : best
      ), 0);
      const target = cards[Math.max(0, Math.min(cards.length - 1, closest + direction))];
      track.scrollTo({ left: target.offsetLeft - start, behavior: scrollBehavior() });
    };
    carousel.querySelector("[data-carousel-prev]")?.addEventListener("click", () => move(-1));
    carousel.querySelector("[data-carousel-next]")?.addEventListener("click", () => move(1));
    track.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
      event.preventDefault(); move(event.key === "ArrowRight" ? 1 : -1);
    });
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

  document.querySelector("[data-share]")?.addEventListener("click", async () => {
    try {
      if (navigator.share) await navigator.share({ title: document.title, url: window.location.href });
      else {
        await navigator.clipboard.writeText(window.location.href);
        showWalkNotice("Ссылка скопирована");
      }
    } catch (error) {
      if (error.name !== "AbortError") showWalkNotice("Не удалось поделиться. Скопируйте адрес из строки браузера.");
    }
  });
})();
