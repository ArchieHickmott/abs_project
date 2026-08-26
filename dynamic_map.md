# Dynamic Map
Dynamically display different statistical area levels dependent on users zoom level within web browser map viewer

## Structure
Each statistical area level with have its own tilemap, these tiles will be precomputed and stored in the database with their:
    minX maxX minY maxY, and foreign keys pointing to polygons in area
each tile is congruent to every tile in its own tilemap
tiles are indexed such that once an initial tile is loaded, adjacent tiles can be loaded without searching for intersections
client will send a request to the server when a new tile is needed
client will load and unload tiles into cache as needed
client will load enough tiles to display in viewport and have as buffer when the screen moves, this way
    there isnt a new request to the server everytime the user slightly moves their screen
server remains stateless and simply returns tiles as requested

## Logic
if viewport "zoom" level crosses threshold for new statistical area then
client requests new data from server, providing viewer center position
server responds with tile index, and the tiles boundary
based on tile size client calculates what tiles are needed for the cache
client requests the tiles needed for cache
server returns tiles and their polygons
client caches the tiles ready to be displayed

if viewport reaches boundary of cached tiles then
client calculates what tiles are needed
client requests tiles that aren't already cached
server returns tules and their polygons 
client caches new tiles
client removes tiles that aren't needed from cache

## Functional Requirements
### Backend
internal util functions
```python
def search_boundaries_in_area(boundary:tuple[tuple[float,float],tuple[float,float]]) -> list[list[tuple[float,float]]]:
    """
    Search geodatabase finding polygons within a rectangular area

    Args:
        boundary (tuple[tuple[float,float],tuple[float,float]]): search boundary
    
    Returns:
        list[list[tuple[float,float]]]: list of polygons that are within search boundary
    """
```

```python
def get_tile_from_point(point:tuple[float,float]) -> int
```

```python
def get_tile_geometry(tile_id:int) -> list[list[tuple[float,float]]]
```

### Frontend
basic data scructures used:
```javascript
type Point = {
    x: number;
    y: number;
};

type Boundary = {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
};

type TileID = number;

type Tile = {
    id: TileID;
    boundary: Boundary;
    polygons: Polygon[];
};

type Polygon = {
    coordinates: Point[];
};
```

```javascript
function calculateTilesForCache(
    tileBoundary: Boundary,
    viewportPosition: Point
): TileID[];
```
calculate_tiles_for_cache() is called once when loading a new cache from scratch, update_cache() is used when the viewport is moved

```javascript
function updateCache(
    viewportPosition: Point
): Promise<void>;
```
update_cache() will remove unneded tiles from the cache and request the server for new tiles based on moved viewport

```javascript
function clearCache(): void;
```
removes all tiles from cache