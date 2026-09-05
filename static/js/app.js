(() => {
  const storageKey = "kidstime:favorites";

  const readFavorites = () => {
    try {
      return new Set(JSON.parse(window.localStorage.getItem(storageKey) || "[]").map(String));
    } catch (_error) {
      return new Set();
    }
  };

  const writeFavorites = (favorites) => {
    window.localStorage.setItem(storageKey, JSON.stringify(Array.from(favorites)));
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
