import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

type StatisticalAreaLevel = 1 | 2 | 3 | 4;

interface Sa1Properties {
    sa1_code: number;
}

interface Sa2Properties {
    sa2_code: number;
}

interface Sa3Properties {
    sa3_code: number;
}

interface Sa4Properties {
    sa4_code: number;
}

type StatisticalAreaProperties =
    | Sa1Properties
    | Sa2Properties
    | Sa3Properties
    | Sa4Properties;

type PropertiesForLevel<L extends StatisticalAreaLevel> =
    L extends 1 ? Sa1Properties :
    L extends 2 ? Sa2Properties :
    L extends 3 ? Sa3Properties :
    Sa4Properties;

interface MultiPolygon {
    type: "MultiPolygon";
    coordinates: number[][][][];
}

interface Feature<
    P extends StatisticalAreaProperties = StatisticalAreaProperties
> {
    type: "Feature";
    id: number;
    properties: P;
    geometry: MultiPolygon;
}

interface FeatureCollection<
    P extends StatisticalAreaProperties = StatisticalAreaProperties
> {
    type: "FeatureCollection";
    features: Feature<P>[];
}

const INITIAL_CENTRE: [number, number] = [133.7751, -25.2744];
const CACHE_MOVE_THRESHOLDS: Record<StatisticalAreaLevel, number> = {1:0.5, 2:1, 3:2, 4:4};
const POLYGON_SOURCE = "statistical-areas";
const POLYGON_FILL_LAYER = "statistical-areas-fill";
const POLYGON_OUTLINE_LAYER = "statistical-areas-outline";

let statisticalAreaLevel: StatisticalAreaLevel = 4;
let lastCacheCentre: [number, number] = INITIAL_CENTRE
let zoomingCacheUpdatePending = false;

function getStatisticalAreaLevel(
    zoom: number
): StatisticalAreaLevel {

    if (zoom < 6.0) {
        return 4;
    }

    if (zoom < 8.0) {
        return 3;
    }

    if (zoom < 11.0) {
        return 2;
    }

    return 1;
}

async function getTilemapCache<L extends StatisticalAreaLevel>(
    level: L,
    longitude: number,
    latitude: number,
): Promise<FeatureCollection<PropertiesForLevel<L>>> {

    const response = await fetch(
        `/tilemap-cache?x=${longitude}&y=${latitude}&level=${level}`
    );

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    return await response.json() as FeatureCollection<
        PropertiesForLevel<L>
    >;
}

function setPolygonData(
    map: maplibregl.Map,
    data: FeatureCollection,
): void {
    const source = map.getSource(
        POLYGON_SOURCE
    ) as maplibregl.GeoJSONSource | undefined;

    if (!source) {
        throw new Error(
            `MapLibre source '${POLYGON_SOURCE}' does not exist`
        );
    }

    source.setData(data);
}

async function loadTileCache(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number,
): Promise<void> {

    console.log(
        `Loading SA${level} cache at ${longitude}, ${latitude}`
    );

    const data = await getTilemapCache(
        level,
        longitude,
        latitude,
    );

    console.log(
        `Received ${data.features.length} unique polygons`
    );

    setPolygonData(map, data);

    lastCacheCentre[0] = longitude;
    lastCacheCentre[1] = latitude;
}

async function updateTileCache(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number,
): Promise<void> {

    const longitudeDifference = Math.abs(
        longitude - lastCacheCentre[0]
    );

    const latitudeDifference = Math.abs(
        latitude - lastCacheCentre[1]
    );

    if (
        longitudeDifference < CACHE_MOVE_THRESHOLDS[level] &&
        latitudeDifference < CACHE_MOVE_THRESHOLDS[level]
    ) {
        return;
    }

    await loadTileCache(
        map,
        level,
        longitude,
        latitude,
    );
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