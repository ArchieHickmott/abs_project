import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

type StatisticalAreaLevel = 1 | 2 | 3 | 4;

const initialCenter: [number, number] = [133.7751, -25.2744];

let statisticalArea: StatisticalAreaLevel = 4;

async function getInitialTile(
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number,
): Promise<string> {
    const response = await fetch(
        `/initial-tile?level=${level}&x=${longitude}&y=${latitude}`,
    );

    if (!response.ok) {
        throw new Error(`HTTP error! Status: ${response.status}`);
    }

    return response.json();
}

async function loadTile(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number,
): Promise<void> {
    const tile = await getInitialTile(level, longitude, latitude);

    const sourceData = `/get-tile-geometries?level=${level}&tile-id=${tile}`;

    // Remove the old source/layers if they exist.
    if (map.getLayer("australia")) {
        map.removeLayer("australia");
    }

    if (map.getLayer("australia-outline")) {
        map.removeLayer("australia-outline");
    }

    if (map.getSource("australia")) {
        map.removeSource("australia");
    }

    map.addSource("australia", {
        type: "geojson",
        data: sourceData,
    });

    map.addLayer({
        id: "australia",
        type: "fill",
        source: "australia",
        paint: {
            "fill-color": "#088",
            "fill-opacity": 0.8,
        },
    });

    map.addLayer({
        id: "australia-outline",
        type: "line",
        source: "australia",
        paint: {
            "line-color": "#ffffff",
            "line-width": 1,
        },
    });
}

function getStatisticalAreaLevel(zoom: number): StatisticalAreaLevel {
    if (zoom < 6.0) {
        return 4;
    } else if (zoom < 8.0) {
        return 3;
    } else if (zoom < 10.0) {
        return 2;
    } else {
        return 1;
    }
}

async function main(): Promise<void> {
    const map = new maplibregl.Map({
        container: "map",
        style: "https://tiles.openfreemap.org/styles/bright",
        center: initialCenter,
        zoom: 4,
    });

    map.on("load", async () => {
        await loadTile(
            map,
            statisticalArea,
            initialCenter[0],
            initialCenter[1],
        );
    });

    map.on("zoom", async () => {
        const oldLevel = statisticalArea;
        const newLevel = getStatisticalAreaLevel(map.getZoom());

        if (newLevel === oldLevel) {
            return;
        }

        statisticalArea = newLevel;

        console.log(
            `Changed statistical area: ${oldLevel} -> ${statisticalArea}`,
        );

        const center = map.getCenter();

        await loadTile(
            map,
            statisticalArea,
            center.lng,
            center.lat,
        );
    });
}

main().catch((error: unknown) => {
    console.error("Failed to initialise map:", error);
});
