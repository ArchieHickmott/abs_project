import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

type StatisticalAreaLevel = 1 | 2 | 3 | 4;

class TileCoordinate {
  x: number;
  y: number;

  constructor(x: number, y: number);
  constructor(id: string);

  constructor(x: number | string, y?: number) {
    if (typeof x === "number") {
      this.x = x;
      if (y === undefined) {
        throw new Error("Argument error, expected both an x and y coordinate to contruct TileCoordinate")
      }
      this.y = y;
    }
    else {
      let coordinates: number[] = x.split("_").map(Number);
      let coordinates_count = coordinates.length
      if (coordinates_count != 2) {
        throw new Error(`Argument error, tile id formated incorrectly ${x}`)
      }
      this.x = coordinates[0];
      this.y = coordinates[1];
    }
  };

  to_string_id(): string {
    return `${this.x}_${this.y}`
  }
}

const initialCenter: [number, number] = [133.7751, -25.2744];

let statisticalArea: StatisticalAreaLevel = 4;

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

    return new TileCoordinate(json);
}

function loadTile(
    map: maplibregl.Map,
    level: StatisticalAreaLevel,
    tile_coordinate: TileCoordinate
): void {
    const tile = tile_coordinate.to_string_id();

    const sourceData = `/get-tile-geometries?level=${level}&tile-id=${tile}`;

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
        const tile: TileCoordinate | null = await getTileId(statisticalArea, initialCenter[0], initialCenter[1])
        if (tile === null) {
          return;
        }
        loadTile(
            map,
            statisticalArea,
            tile
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

        const tile: TileCoordinate | null = await getTileId(statisticalArea, center.lng, center.lat)
        if (tile === null) {
          return;
        }
        loadTile(
            map,
            statisticalArea,
            tile
        );
    });
}

main().catch((error: unknown) => {
    console.error("Failed to initialise map:", error);
});
