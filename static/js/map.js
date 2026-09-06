const root = document.querySelector("[data-map-root]");
const unavailable = document.querySelector("[data-map-unavailable]");

if (!root || root.dataset.mapEnabled !== "true" || !window.ymaps3) {
  if (unavailable) unavailable.hidden = false;
} else {
  try {
    const response = await fetch(root.dataset.endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error("Не удалось загрузить события для карты");
    const payload = await response.json();

    await window.ymaps3.ready;
    const { YMap, YMapDefaultSchemeLayer, YMapDefaultFeaturesLayer, YMapMarker } = window.ymaps3;

    const map = new YMap(document.getElementById("events-map"), {
      location: { center: [37.6176, 55.7558], zoom: 10 },
      behaviors: ["drag", "scrollZoom", "pinchZoom", "dblClick"],
    });
    map.addChild(new YMapDefaultSchemeLayer({}));
    map.addChild(new YMapDefaultFeaturesLayer({}));

    const sheet = document.querySelector("[data-map-sheet]");
    const showEvent = (event) => {
      if (!sheet) return;
      sheet.querySelector("[data-map-sheet-image]").src = event.cover || "";
      sheet.querySelector("[data-map-sheet-category]").textContent = event.category;
      sheet.querySelector("[data-map-sheet-title]").textContent = event.title;
      sheet.querySelector("[data-map-sheet-address]").textContent = event.address;
      sheet.querySelector("[data-map-sheet-age]").textContent = event.age;
      sheet.querySelector("[data-map-sheet-price]").textContent = event.price;
      sheet.querySelector("[data-map-sheet-link]").href = event.url;
      sheet.querySelector("[data-map-sheet-route]").href = `https://yandex.ru/maps/?rtext=~${encodeURIComponent(`${event.lat},${event.lng}`)}&rtt=auto`;
      const walkButton = sheet.querySelector("[data-map-sheet-walk]");
      walkButton.dataset.walkButton = String(event.id);
      window.KidsTimeWalk?.refreshButton(walkButton);
      sheet.hidden = false;
    };

    payload.results.forEach((event) => {
      const marker = document.createElement("button");
      marker.className = "map-marker";
      marker.type = "button";
      marker.setAttribute("aria-label", event.title);
      marker.innerHTML = "<span></span>";
      marker.addEventListener("click", () => showEvent(event));
      map.addChild(new YMapMarker({ coordinates: [event.lng, event.lat] }, marker));
    });

    document.querySelector("[data-map-sheet-close]")?.addEventListener("click", () => {
      if (sheet) sheet.hidden = true;
    });
  } catch (error) {
    console.error(error);
    if (unavailable) {
      unavailable.hidden = false;
      unavailable.querySelector("strong").textContent = "Карта временно недоступна";
      unavailable.querySelector("p").textContent = "Откройте список мероприятий и попробуйте ещё раз позже.";
    }
  }
}
