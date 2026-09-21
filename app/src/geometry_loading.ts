import * as maplibregl from "maplibre-gl";

export type StatisticalAreaLevel = 1 | 2 | 3 | 4;

export interface Sa1Properties {
    sa1_code: number;
}

export interface Sa2Properties {
    sa2_code: number;
}

export interface Sa3Properties {
    sa3_code: number;
}

export interface Sa4Properties {
    sa4_code: number;
}

export type StatisticalAreaProperties =
    | Sa1Properties
    | Sa2Properties
    | Sa3Properties
    | Sa4Properties;

export type PropertiesForLevel<L extends StatisticalAreaLevel> =
    L extends 1 ? Sa1Properties :
    L extends 2 ? Sa2Properties :
    L extends 3 ? Sa3Properties :
    Sa4Properties;

export interface MultiPolygon {
    type: "MultiPolygon";
    coordinates: number[][][][];
}

export interface Feature<
    P extends StatisticalAreaProperties = StatisticalAreaProperties
> {
    type: "Feature";
    id: number;
    properties: P;
    geometry: MultiPolygon;
}

export interface FeatureCollection<
    P extends StatisticalAreaProperties = StatisticalAreaProperties
> {
    type: "FeatureCollection";
    features: Feature<P>[];
}

export const INITIAL_CENTRE: [number, number] = [133.7751, -25.2744];
export const CACHE_MOVE_THRESHOLDS: Record<StatisticalAreaLevel, number> = {1:0.5, 2:1, 3:2, 4:4};
export const POLYGON_SOURCE = "statistical-areas";

export let statisticalAreaLevel: StatisticalAreaLevel = 4;
export let lastCacheCentre: [number, number] = INITIAL_CENTRE

export function getStatisticalAreaLevel(
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

export async function getTilemapCache<L extends StatisticalAreaLevel>(
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

export function setPolygonData(
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

export async function loadTileCache(
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

export async function updateTileCache(
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