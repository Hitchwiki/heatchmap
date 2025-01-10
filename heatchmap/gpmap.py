"""Module to recalculate the map with the current Gaussian Process model."""
import glob
import os
import pickle
import time
import requests
import zipfile
import io

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from huggingface_hub import hf_hub_download
from matplotlib import pyplot as plt
from rasterio.control import GroundControlPoint as GCP
from rasterio.crs import CRS
from rasterio.transform import from_gcps
from shapely.validation import make_valid
from tqdm import tqdm
from datasets import load_dataset

from .map_based_model import MapBasedModel
from .utils.utils_data import get_points
from .utils.utils_models import fit_gpr_silent


HERE = os.path.dirname(os.path.abspath(__file__))


class GPMap(MapBasedModel):
    def __init__(self, region="world", resolution=10, version="prod"):
        os.makedirs(f"{HERE}/cache/hitchmap", exist_ok=True)
        self.points_path = f"{HERE}/cache/hitchmap/dump.sqlite"
        hitchmap_url = 'https://hitchmap.com/dump.sqlite'
        response = requests.get(hitchmap_url)
        response.raise_for_status()  # Check for HTTP request errors
        with open(self.points_path, "wb") as file:
            file.write(response.content)
            print(f"Downloaded Hitchmap data to: {self.points_path}")

        if os.path.exists("models/kernel.pkl"):
            self.gpr_path = "models/kernel.pkl"
        else:
            REPO_ID = "tillwenke/heatchmap-model"
            FILENAME = "Unfitted_GaussianProcess_TransformedTargetRegressorWithUncertainty.pkl"
            self.gpr_path = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
            
        with open(self.gpr_path, "rb") as file:
            self.gpr = pickle.load(file)

        super().__init__(method=type(self.gpr).__name__, region=region, resolution=resolution, version=version, verbose=False)
        
        ds = load_dataset("tillwenke/heatchmap-map", cache_dir=f"{HERE}/cache/huggingface")
        ds = ds.with_format("np")
        self.raw_raster = ds["train"]["numpy"]
        
        # files = glob.glob(f"intermediate/map_{self.method}_{self.region}_{self.resolution}_{self.version}*.txt")

        self.begin = pd.Timestamp("2024-12-21") # TODO: read latest date from somewhere

        self.batch_size = 10000
        self.today = pd.Timestamp.now()
        # self.map_path = f"intermediate/map_{self.method}_{self.region}_{self.resolution}_{self.version}_{self.today.date()}.txt"
        

        self.recalc_radius = 800000 # TODO: determine from model largest influence radius
        
        
        self.shapely_countries = f"{HERE}/cache/countries/ne_110m_admin_0_countries.shp"

        if not os.path.exists(self.shapely_countries):
            output_dir = f"{HERE}/cache/countries"
            os.makedirs(output_dir, exist_ok=True)

            # URL for the 110m countries shapefile from Natural Earth
            url = "https://naturalearth.s3.amazonaws.com/110m_cultural/ne_110m_admin_0_countries.zip"

            # Directory to save the dataset
            

            # Download the dataset
            print("Downloading countries dataset...")
            response = requests.get(url)
            response.raise_for_status()  # Raise an error for bad responses

            # Extract the zip file
            print("Extracting files...")
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                z.extractall(output_dir)

            print(f"Countries dataset downloaded and extracted to: {output_dir}")
        
        else:
            print(f"Countries dataset already exists at: {self.shapely_countries}")

    def recalc_map(self):
        """Recalculate the map with the current Gaussian Process model.

        Overrides the stored np.array raster of the map.
        """
        # fit model to new data points

        self.points = get_points(self.points_path, until=self.today)
        self.points["lon"] = self.points.geometry.x
        self.points["lat"] = self.points.geometry.y

        X = self.points[["lon", "lat"]].values
        y = self.points["wait"].values  

        self.gpr.regressor.optimizer = None
        self.gpr = fit_gpr_silent(self.gpr, X, y)

        # recalc the old map

        # self.raw_raster = np.loadtxt(self.old_map_path)

        self.get_map_grid()
        self.get_recalc_raster()

        print("Compute pixels that are expected to differ...")
        start = time.time()
        to_predict = []
        pixels_to_predict = []
        for x, vertical_line in tqdm(
            enumerate(self.grid.transpose()), total=len(self.grid.transpose())
        ):
            for y, coords in enumerate(vertical_line):
                if self.recalc_raster[y][x] == 0:
                    continue
                this_point = [float(coords[0]), float(coords[1])]
                to_predict.append(this_point)
                pixels_to_predict.append((y, x))
                # batching the model calls
                if len(to_predict) == self.batch_size:
                    prediction = self.gpr.predict(np.array(to_predict), return_std=False)
                    for i, (y, x) in enumerate(pixels_to_predict):
                        self.raw_raster[y][x] = prediction[i]

                    to_predict = []
                    pixels_to_predict = []
        
        if len(to_predict) > 0:
            prediction = self.gpr.predict(np.array(to_predict), return_std=False)
            for i, (y, x) in enumerate(pixels_to_predict):
                self.raw_raster[y][x] = prediction[i]

        print(f"Time elapsed to compute full map: {time.time() - start}")
        print(
            f"For map of shape: {self.raw_raster.shape} that is {self.raw_raster.shape[0] * self.raw_raster.shape[1]} pixels and an effective time per pixel of {(time.time() - start) / (self.raw_raster.shape[0] * self.raw_raster.shape[1])} seconds"
        )
        print(f"Only {self.recalc_raster.sum()} pixels were recalculated. That is {self.recalc_raster.sum() / (self.raw_raster.shape[0] * self.raw_raster.shape[1]) * 100}% of the map.")
        print(f"And time per recalculated pixel was {(time.time() - start) / self.recalc_raster.sum()} seconds")

        # np.savetxt(self.map_path, self.raw_raster)
        # self.save_as_rasterio()

    def show_raster(self, raster: np.array):
        """Show the raster in a plot.
        
        Args:
            raster (np.array): 2D np.array of the raster to be shown.

        """
        plt.imshow(raster, cmap="viridis", interpolation="nearest")
        plt.colorbar()
        plt.xlabel("Longitude")
        plt.ylabel("Latitude")
        plt.show()

    def pixel_from_point(self, point) -> tuple[int, int]:
        """For a given point by coordinates, determines the pixel in the raster that best corresponds to it."""
        lats = self.Y.transpose()[0]
        lat_index = None
        for i, lat in enumerate(lats):
            if lat >= point["lat"] and point["lat"] >= lats[i+1]:
                lat_index = i
                break

        lons = self.X[0]
        lon_index = None
        for i, lon in enumerate(lons):
            if lon <= point["lon"] and point["lon"] <= lons[i+1]:
                lon_index = i
                break

        result = (lat_index, lon_index)

        return result
        
    def get_recalc_raster(self):
        """Creats 2d np.array of raster where only pixels that are 1 should be recalculated."""
        recalc_radius_pixels = int(np.ceil(abs(self.recalc_radius / (self.grid[0][0][0] - self.grid[0][0][1]))))

        self.recalc_raster = np.zeros(self.grid.shape[1:])

        new_points = get_points(self.points_path, begin=self.begin, until=self.today)
        new_points["lon"] = new_points.geometry.x
        new_points["lat"] = new_points.geometry.y
        print(f"Recalculating map for {len(new_points)} new points.")
        for i, point in new_points.iterrows():
            lat_pixel, lon_pixel = self.pixel_from_point(point)

            for i in range(lat_pixel - recalc_radius_pixels, lat_pixel + recalc_radius_pixels):
                for j in range(lon_pixel - recalc_radius_pixels, lon_pixel + recalc_radius_pixels):
                    if i < 0 or j < 0 or i >= self.recalc_raster.shape[0] or j >= self.recalc_raster.shape[1]:
                        continue
                    self.recalc_raster[i, j] = 1
        self.show_raster(self.recalc_raster)
        
        print("Report reduction of rasters.")
        print(self.recalc_raster.sum(), self.recalc_raster.shape[0] * self.recalc_raster.shape[1], self.recalc_raster.sum() / (self.recalc_raster.shape[0] * self.recalc_raster.shape[1]))
        self.get_landmass_raster()
        self.recalc_raster = self.recalc_raster * self.landmass_raster
        self.show_raster(self.recalc_raster)
        print(self.landmass_raster.sum(), self.landmass_raster.shape[0] * self.landmass_raster.shape[1], self.landmass_raster.sum() / (self.landmass_raster.shape[0] * self.landmass_raster.shape[1]))
        print(self.recalc_raster.sum(), self.recalc_raster.shape[0] * self.recalc_raster.shape[1], self.recalc_raster.sum() / (self.recalc_raster.shape[0] * self.recalc_raster.shape[1]))

    def get_landmass_raster(self):
        """Creates raster of landmass as np.array"""
        self.landmass_raster = np.ones(self.grid.shape[1:])

        polygon_vertices_x, polygon_vertices_y, pixel_width, pixel_height = (
            self.define_raster()
        )

        # handling special case when map spans over the 180 degree meridian
        if polygon_vertices_x[0] > 0 and polygon_vertices_x[2] < 0:
            polygon_vertices_x[2] = 2 * MERIDIAN + polygon_vertices_x[2]
            polygon_vertices_x[3] = 2 * MERIDIAN + polygon_vertices_x[3]

        # https://gis.stackexchange.com/questions/425903/getting-rasterio-transform-affine-from-lat-and-long-array

        # lower/upper - left/right
        ll = (polygon_vertices_x[0], polygon_vertices_y[0])
        ul = (polygon_vertices_x[1], polygon_vertices_y[1])  # in lon, lat / x, y order
        ur = (polygon_vertices_x[2], polygon_vertices_y[2])
        lr = (polygon_vertices_x[3], polygon_vertices_y[3])
        cols, rows = pixel_width, pixel_height

        # ground control points
        gcps = [
            GCP(0, 0, *ul),
            GCP(0, cols, *ur),
            GCP(rows, 0, *ll),
            GCP(rows, cols, *lr),
        ]

        # seems to need the vertices of the map polygon
        transform = from_gcps(gcps)

        # cannot use np.float128 to write to tif
        self.landmass_raster = self.landmass_raster.astype(np.float64)

        # save the colored raster using the above transform
        # important: rasterio requires [0,0] of the raster to be in the upper left corner and [rows, cols] in the lower right corner
        # TODO find out why raster is getting smaller in x direction when stored as tif (e.g. 393x700 -> 425x700)
        with rasterio.open(
            self.landmass_path,
            "w",
            driver="GTiff",
            height=self.landmass_raster.shape[0],
            width=self.landmass_raster.shape[1],
            count=1,
            crs=CRS.from_epsg(3857),
            transform=transform,
            dtype=self.landmass_raster.dtype,
        ) as destination:
            destination.write(self.landmass_raster, 1)

        landmass_rasterio = rasterio.open(self.landmass_path)

        nodata = 0

        countries = gpd.read_file(self.shapely_countries)
        countries = countries.to_crs(epsg=3857)
        countries = countries[countries.NAME != "Antarctica"]
        country_shapes = countries.geometry
        country_shapes = country_shapes.apply(lambda x: make_valid(x))

        out_image, out_transform = rasterio.mask.mask(
            landmass_rasterio, country_shapes, nodata=nodata
        )

        self.landmass_raster = out_image[0]
        self.show_raster(self.landmass_raster)

        # cleanup
        os.remove(self.landmass_path)


def recalc():
    gpmap = GPMap(resolution=1)
    gpmap.recalc_map()
