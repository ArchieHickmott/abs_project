import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

type StatisticalAreaLevel = 1 | 2 | 3 | 4;

class TileCoordinate {
    x: number;
    y: number;

    constructor(x: number, y: number) {
        this.x = x;
        this.y = y;
    }

    static fromTileId(tile_id: string) {
        let coordinates: number[] = tile_id.split("_").map(Number);
        let coordinates_count = coordinates.length;
        if (coordinates_count != 2) {
            throw new Error(`Argument error, tile id formated incorrectly ${tile_id}`);
        }
        return new TileCoordinate(coordinates[0], coordinates[1]);
    }

    toStringId(): string {
        return `${this.x}_${this.y}`
    }
}

class Tile {
    id: string;
    coordinate: TileCoordinate;
    statistical_area: StatisticalAreaLevel;

    source_name: string;
    layer_name: string; 
    outline_name: string;
    label_name: string;

    constructor(coordinate: TileCoordinate, statistical_area: StatisticalAreaLevel) {
        this.id = coordinate.toStringId();
        this.coordinate = coordinate;
        this.statistical_area = statistical_area;
        this.source_name = `SA${statistical_area}_${coordinate.toStringId()}`;
        this.layer_name = this.source_name + "-background";
        this.outline_name = this.source_name + "-outline";
        this.label_name = this.source_name + "-label"    
    }

    static fromSourceName(source_name: string): Tile {
        const match = source_name.match(/^SA(\d+)_(.+)$/);

        if (!match) {
            throw new Error(
                `Argument error, source name formatted incorrectly: ${source_name}`
            );
        }

        const level = Number(match[1]);
        const tile_id = match[2];

        const coordinate = TileCoordinate.fromTileId(tile_id);

        return new Tile(
            coordinate,
            level as StatisticalAreaLevel
        );
    }
}
const initialCenter: [number, number] = [133.7751, -25.2744];
const tileRenderRadius= {1:2, 2:2, 3:5, 4:10};
const cacheMoveThreshold = {1:0.5, 2:1, 3:2, 4:4};


let statisticalArea: StatisticalAreaLevel = 4;
let tileCache: Set<string> = new Set();
let lastCacheLongitude = initialCenter[0];
let lastCacheLatitude = initialCenter[1];
let zooming = false; // tells map.on("moveend") that moveTileCache doesnt need to be called as the tiles have been reloaded

async function getTileId(
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number,
): Promise<TileCoordinate | null> {
    const response = await fetch(
        `/tile-id?level=${level}&x=${longitude}&y=${latitude}`,
    );

    if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`);
    }

    const json: string | null = await response.json();
    if (json === null) {
        return null;
    }

    return TileCoordinate.fromTileId(json);
}

function loadTile(
    map: maplibregl.Map,
    tile: Tile
): void {
    const source_data = `/get-tile-geometries?level=${tile.statistical_area}&tile-id=${tile.id}`;

    console.log(`loading_tile: ${tile.id}`)

    unloadTile(map, tile);

    map.addSource(tile.source_name, {
        type: "geojson",
        data: source_data,
    });

    map.addLayer({
        id: tile.layer_name,
        type: "fill",
        source: tile.source_name,
        paint: {
            "fill-color": "#088",
            "fill-opacity": 0.8,
        },
    });

    map.addLayer({
        id: tile.outline_name,
        type: "line",
        source: tile.source_name,
        paint: {
            "line-color": "#ffffff",
            "line-width": 1,
        },
    });

    map.addLayer({
        id: tile.label_name,
        type: "symbol",
        source: tile.source_name,
        layout: {
            "text-field": ["get", "tile_id"],
            "text-size": 16,
            "text-allow-overlap": true,
        },
        paint: {
            "text-color": "#ffffff",
            "text-halo-color": "#000000",
            "text-halo-width": 2,
        },
    });

    tileCache.add(tile.source_name);
}

function unloadTile(
    map: maplibregl.Map,
    tile: Tile
): void {
    if (map.getLayer(tile.layer_name)) {
        map.removeLayer(tile.layer_name);
    }

    if (map.getLayer(tile.outline_name)) {
        map.removeLayer(tile.outline_name);
    }

    if (map.getLayer(tile.label_name)) {
        map.removeLayer(tile.label_name);
    }

    if (map.getSource(tile.source_name)) {
        map.removeSource(tile.source_name);
    }
    tileCache.delete(tile.source_name);
}

function getTileCacheList(initial_tile: TileCoordinate, level: StatisticalAreaLevel): Tile[] {
    const radius = tileRenderRadius[level];
    const tiles: { tile: TileCoordinate; distance: number }[] = [];
    const radius_squared = radius * radius;

    for (
        let x = initial_tile.x - radius;
        x <= initial_tile.x + radius;
        x++
    ) {
        if (x < 0) {
            continue;
        }
        for (
            let y = initial_tile.y - radius;
            y <= initial_tile.y + radius;
            y++
        ) {
            if (y < 0) {
                continue;
            }
            const dx = x - initial_tile.x;
            const dy = y - initial_tile.y;
            const distance = dx * dx + dy * dy;

            if (distance <= radius_squared) {

                tiles.push({
                    tile: new TileCoordinate(x, y),
                    distance,
                });
            }
        }
    }

    tiles.sort((a, b) => a.distance - b.distance);

    return tiles.map(x => new Tile(x.tile, level));
}

function getStatisticalAreaLevel(zoom: number): StatisticalAreaLevel {
    if (zoom < 6.0) {
        return 4;
    } else if (zoom < 8.0) {
        return 3;
    } else if (zoom < 11.0) {
        return 2;
    } else {
        return 1;
    }
}

function clearTileCache(map: maplibregl.Map) {
    tileCache.forEach(tile => unloadTile(map, Tile.fromSourceName(tile)))
}

async function newTileCache(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number
): Promise<void> {
    clearTileCache(map);
    const center_tile: TileCoordinate | null = await getTileId(statisticalArea, longitude, latitude)
    if (center_tile === null) {
        return;
    }
    let tile_cache = getTileCacheList(center_tile, level);
    console.log(`${tile_cache.map(tile => tile.id)}`)
    for (const tile of tile_cache) {
        loadTile(
            map,
            tile
        )
    }
}

async function moveTileCache(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    longitude: number,
    latitude: number    
): Promise<void> {
    if (level === 4) {
        return;
    }

    const center_tile: TileCoordinate | null = await getTileId(level, longitude, latitude)

    if (center_tile === null) {
        return;
    }

    const new_tile_cache = new Set(
        getTileCacheList(center_tile, level).map(tile => tile.source_name)
    );
    console.log(" ");
    console.log(new_tile_cache == tileCache);
    const tiles_to_load = new Set(
        [...new_tile_cache].filter(tile => !tileCache.has(tile))
    );;
    const tiles_to_unload = new Set(
        [...tileCache].filter(tile => !new_tile_cache.has(tile))
    );

    tiles_to_unload.forEach((tile) => unloadTile(map, Tile.fromSourceName(tile)))
    tiles_to_load.forEach((tile) => loadTile(map, Tile.fromSourceName(tile)))
}

async function main(): Promise<void> {
    const map = new maplibregl.Map({
        container: "map",
        style: "https://tiles.openfreemap.org/styles/bright",
        center: initialCenter,
        zoom: 4,
    });

    map.on("load", async () => {return await newTileCache(map, statisticalArea, initialCenter[0], initialCenter[1]);});

    map.on("zoom", async () => {
        // zooming = true;

        const oldLevel = statisticalArea;
        const newLevel = getStatisticalAreaLevel(map.getZoom()); 

        if (newLevel === oldLevel) {
            return;
        }

        statisticalArea = newLevel;

        const center = map.getCenter();

        console.log(`[${center.lng}, ${center.lat}]`)

        await newTileCache(map, statisticalArea, center.lng, center.lat);
        zooming = false;
    });

    map.on("moveend", async () => {
        if (zooming) {
            return;
        }
        const center = map.getCenter();

        const longitudeDifference = Math.abs(
            center.lng - lastCacheLongitude
        );
    
        const latitudeDifference = Math.abs(
            center.lat - lastCacheLatitude
        );
    
        if (
            longitudeDifference < cacheMoveThreshold[statisticalArea] &&
            latitudeDifference < cacheMoveThreshold[statisticalArea]
        ) {
            return;
        }
    
        lastCacheLongitude = center.lng;
        lastCacheLatitude = center.lat;
    
        await moveTileCache(
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
