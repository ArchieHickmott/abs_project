"use strict";
const map = new maplibregl.Map({
    container: "map",
    style: "https://demotiles.maplibre.org/style.json",
    center: [153.0251, -27.4698],
    zoom: 10,
});
map.addControl(new maplibregl.NavigationControl());
new maplibregl.Marker()
    .setLngLat([153.0251, -27.4698])
    .setPopup(new maplibregl.Popup().setHTML("<h3>Brisbane</h3><p>MapLibre is working!</p>"))
    .addTo(map);
