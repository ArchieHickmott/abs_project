import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

import {
    POLYGON_SOURCE,
    INITIAL_CENTRE,
    StatisticalAreaLevel,
    loadTileCache,
    getStatisticalAreaLevel,
    updateTileCache,
} from "./geometry_loading";

const POLYGON_FILL_LAYER = "statistical-areas-fill";
const POLYGON_OUTLINE_LAYER = "statistical-areas-outline";

let statisticalAreaLevel: StatisticalAreaLevel = 4;
let zoomingCacheUpdatePending = false;

function showStatisticalAreaPopup(
    map: maplibregl.Map,
    event: maplibregl.MapMouseEvent & {
        features?: maplibregl.MapGeoJSONFeature[];
    },
): void {
    const feature = event.features?.[0];

    if (!feature) {
        return;
    }

    const codeProperty = `sa${statisticalAreaLevel}_code`;

    const properties = feature.properties as Record<
        string,
        string | number | null
    >;

    const code = properties[codeProperty];

    if (code === undefined || code === null) {
        return;
    }

    new maplibregl.Popup()
        .setLngLat(event.lngLat)
        .setHTML(`
            <strong>SA${statisticalAreaLevel}</strong><br>
            Code: ${code}
        `)
        .addTo(map);
}

async function main(): Promise<void> {
    const map = new maplibregl.Map({
        container: "map",
        style: "https://tiles.openfreemap.org/styles/bright",
        center: INITIAL_CENTRE,
        zoom: 4,
    });

    map.on("load", async () => {
        map.addSource(POLYGON_SOURCE, {
            type: "geojson",
            data: {
                type: "FeatureCollection",
                features: [],
            },
        });

        map.addLayer({
            id: POLYGON_FILL_LAYER,
            type: "fill",
            source: POLYGON_SOURCE,
            paint: {
                "fill-color": "#088",
                "fill-opacity": 0.8,
            },
        });

        map.addLayer({
            id: POLYGON_OUTLINE_LAYER,
            type: "line",
            source: POLYGON_SOURCE,
            paint: {
                "line-color": "#ffffff",
                "line-width": 1,
            },
        });
    
        map.on("click", POLYGON_FILL_LAYER, (event) => {
            showStatisticalAreaPopup(map, event);
        });
    
        map.on("mouseenter", POLYGON_FILL_LAYER, () => {
            map.getCanvas().style.cursor = "pointer";
        });
    
        map.on("mouseleave", POLYGON_FILL_LAYER, () => {
            map.getCanvas().style.cursor = "";
        });

        await loadTileCache(
            map,
            statisticalAreaLevel,
            INITIAL_CENTRE[0],
            INITIAL_CENTRE[1],
        );
    });

    map.on("zoomend", async () => {
        const oldLevel = statisticalAreaLevel;
        const newLevel = getStatisticalAreaLevel(
            map.getZoom()
        );
        if (newLevel === oldLevel) {
            return;
        }

        statisticalAreaLevel = newLevel;
        const centre = map.getCenter();

        zoomingCacheUpdatePending = true;

        try {
            await loadTileCache(
                map,
                statisticalAreaLevel,
                centre.lng,
                centre.lat,
            );
        } finally {
            zoomingCacheUpdatePending = false;
        }
    });

    map.on("moveend", async () => {
        if (zoomingCacheUpdatePending) {
            return;
        }

        const centre = map.getCenter();

        await updateTileCache(
            map,
            statisticalAreaLevel,
            centre.lng,
            centre.lat,
        );
    });
}

main().catch((error: unknown) => {
    console.error("Failed to initialise map:", error);
});