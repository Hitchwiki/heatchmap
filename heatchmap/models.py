"""Collection of other simple models."""
import logging

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin
from tqdm.auto import tqdm

from .map_based_model import MapBasedModel

tqdm.pandas()

RESOLUTION = 2

# 180 degree meridian in epsg 3857
MERIDIAN = 20037508

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Average(BaseEstimator, RegressorMixin):
    def __init__(self):
        pass

    def fit(self, X, y):
        self.mean = np.mean(y)

        return self

    def predict(self, X):
        return np.ones(X.shape[0]) * self.mean


class Tiles(MapBasedModel):
    def __init__(self, region="world", tile_size=300000):
        self.region = region
        self.tile_size = tile_size  # in meters

    def get_tile_intervals(self, min, max):
        intervals = [min]
        while (max - min) > self.tile_size:
            new_interval_bound = min + self.tile_size
            intervals.append(new_interval_bound)
            min = new_interval_bound

        intervals.append(max)

        return intervals

    def create_tiles(self):
        xx, yy = self.map_polygon.exterior.coords.xy
        lon_min = xx[0]
        lon_max = xx[3]
        lat_min = yy[0]
        lat_max = yy[1]

        self.lon_intervals = self.get_tile_intervals(lon_min, lon_max)
        self.lat_intervals = self.get_tile_intervals(lat_min, lat_max)

        tiles = np.zeros((len(self.lon_intervals) - 1, len(self.lat_intervals) - 1))

        return tiles

    def get_interval_num(self, intervals, value):
        for i in range(len(intervals) - 1):
            if value >= intervals[i] and value <= intervals[i + 1]:
                return i

    def fit(self, X, y):
        self.map_boundary = self.get_map_boundary()
        self.map_polygon = self.map_to_polygon()
        self.tiles = self.create_tiles()

        points_per_tile = np.zeros(self.tiles.shape)

        for x, single_y in zip(X, y):
            lon, lat = x
            lon_num = self.get_interval_num(self.lon_intervals, lon)
            lat_num = self.get_interval_num(self.lat_intervals, lat)

            self.tiles[lon_num][lat_num] += single_y
            points_per_tile[lon_num][lat_num] += 1

        # average
        points_per_tile = np.where(points_per_tile == 0, 1, points_per_tile)
        self.tiles = self.tiles / points_per_tile

        return self

    def predict(self, X):
        predictions = []

        for x in X:
            lon, lat = x
            lon_num = self.get_interval_num(self.lon_intervals, lon)
            lat_num = self.get_interval_num(self.lat_intervals, lat)
            predictions.append(self.tiles[lon_num][lat_num])

        return np.array(predictions)