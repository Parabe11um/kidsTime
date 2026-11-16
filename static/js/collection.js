const locate = document.querySelector("[data-collection-locate]");
const locationStatus = document.querySelector("[data-collection-status]");

if (locate && navigator.geolocation) {
  locate.hidden = false;
  document.querySelector("[data-collection-location]").hidden = true;
  const useLocation = () => {
    locate.disabled = true;
    locationStatus.textContent = "Определяем местоположение…";
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const url = new URL(window.location.href);
        // The collection uses a five-kilometre radius, so block-level accuracy is enough.
        url.searchParams.set("lat", coords.latitude.toFixed(3));
        url.searchParams.set("lng", coords.longitude.toFixed(3));
        url.searchParams.delete("page");
        window.location.assign(url.toString());
      },
      () => {
        locate.disabled = false;
        locationStatus.textContent = "Не удалось определить местоположение.";
      },
      { timeout: 10000, maximumAge: 60000 },
    );
  };
  locate.addEventListener("click", useLocation);
  if (locate.hasAttribute("data-auto-locate")) {
    useLocation();
  }
}
