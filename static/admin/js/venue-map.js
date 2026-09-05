(() => {
    const root = document.querySelector("[data-venue-map]");
    if (!root) return;

    const container = root.querySelector("[data-venue-map-container]");
    const status = root.querySelector("[data-venue-map-status]");
    const clearButton = root.querySelector("[data-venue-map-clear]");
    const latitudeInput = document.getElementById("id_latitude");
    const longitudeInput = document.getElementById("id_longitude");
    const defaultCoordinates = [37.6176, 55.7558];
    let map = null;
    let marker = null;

    const parsedCoordinates = () => {
        const latitude = Number.parseFloat(latitudeInput?.value);
        const longitude = Number.parseFloat(longitudeInput?.value);
        if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
        return [longitude, latitude];
    };

    const setStatus = (message) => {
        if (status) status.textContent = message;
    };

    const setInputs = (coordinates) => {
        if (!latitudeInput || !longitudeInput) return;
        longitudeInput.value = coordinates[0].toFixed(6);
        latitudeInput.value = coordinates[1].toFixed(6);
        longitudeInput.dispatchEvent(new Event("change", {bubbles: true}));
        latitudeInput.dispatchEvent(new Event("change", {bubbles: true}));
        setStatus(`Выбрано: ${latitudeInput.value}, ${longitudeInput.value}`);
    };

    clearButton?.addEventListener("click", () => {
        if (latitudeInput) latitudeInput.value = "";
        if (longitudeInput) longitudeInput.value = "";
        if (marker && map) {
            map.removeChild(marker);
            marker = null;
        }
        setStatus("Координаты очищены. Выберите новую точку на карте.");
    });

    const init = async () => {
        if (!latitudeInput || !longitudeInput || !container) {
            setStatus("Поля координат не найдены.");
            return;
        }
        if (root.dataset.mapEnabled !== "true") {
            setStatus("Добавьте YANDEX_MAPS_API_KEY в .env. Координаты пока можно ввести вручную.");
            return;
        }
        if (!window.ymaps3) {
            setStatus("API Яндекс Карт ещё не загрузился. Координаты можно ввести вручную.");
            return;
        }

        try {
            await window.ymaps3.ready;
            const {
                YMap,
                YMapDefaultFeaturesLayer,
                YMapDefaultSchemeLayer,
                YMapListener,
                YMapMarker,
            } = window.ymaps3;
            const initialCoordinates = parsedCoordinates();
            map = new YMap(container, {
                location: {
                    center: initialCoordinates || defaultCoordinates,
                    zoom: initialCoordinates ? 15 : 10,
                },
            });
            map.addChild(new YMapDefaultSchemeLayer({}));
            map.addChild(new YMapDefaultFeaturesLayer({}));

            const placeMarker = (coordinates) => {
                if (marker) {
                    marker.update({coordinates});
                } else {
                    const markerElement = document.createElement("div");
                    markerElement.className = "venue-map-marker";
                    marker = new YMapMarker({coordinates}, markerElement);
                    map.addChild(marker);
                }
                setInputs(coordinates);
            };

            map.addChild(new YMapListener({
                layer: "any",
                onClick: (_object, event) => placeMarker(event.coordinates),
            }));

            if (initialCoordinates) placeMarker(initialCoordinates);
            setStatus(initialCoordinates ? "Текущая точка загружена." : "Нажмите на карту, чтобы выбрать точку.");
        } catch (error) {
            console.error("KidsTime venue map initialization failed", error);
            setStatus("Карта не загрузилась. Координаты можно ввести вручную.");
        }
    };

    init();
})();
