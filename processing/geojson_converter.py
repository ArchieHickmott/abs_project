import geopandas as gpd
import os
import sys

def shapefile_to_geojson(shapefile_path, geojson_path):
    """
    Convert a Shapefile to GeoJSON format.
    
    :param shapefile_path: Path to the input .shp file
    :param geojson_path: Path to the output .geojson file
    """
    try:
        # Validate input file
        if not os.path.isfile(shapefile_path):
            raise FileNotFoundError(f"Shapefile not found: {shapefile_path}")
        if not shapefile_path.lower().endswith(".shp"):
            raise ValueError("Input file must have a .shp extension.")

        # Read the shapefile
        gdf = gpd.read_file(shapefile_path)

        # Ensure CRS is set 
        if gdf.crs is None:
            raise ValueError("Shapefile has no Coordinate Reference System (CRS) defined.")
        gdf = gdf.to_crs(epsg=4326)  # WGS84

        # Save as GeoJSON
        gdf.to_file(geojson_path, driver="GeoJSON")
        print(f"Conversion successful! GeoJSON saved at: {geojson_path}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Example usage
    input_shp = input("file_path: ")       
    output_geojson = input_shp.replace("shp", "geojson") 

    shapefile_to_geojson(input_shp, output_geojson)