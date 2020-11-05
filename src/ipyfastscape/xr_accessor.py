from typing import Dict, Tuple

import numpy as np
import pandas as pd
import xarray as xr


@xr.register_dataset_accessor('_widgets')
class WidgetsAccessor:
    """Internal xarray.Dataset extension that stores extra state + implement some
    useful methods for interacting with widgets.

    """

    def __init__(self, dataset: xr.Dataset):
        self._dataset = dataset

        self._data_vars = None
        self._view = None
        self._view_step = None
        self._timestep = 0
        self._extra_dims = None

    def __call__(self, x_dim='x', y_dim='y', time_dim=None, elevation_var='topography__elevation'):

        if elevation_var not in self._dataset:
            raise ValueError(f"variable '{elevation_var}' not found in Dataset")

        elevation_da = self._dataset[elevation_var]
        elevation_dims = set(elevation_da.dims)

        if time_dim is not None:
            if time_dim not in self._dataset.coords:
                raise ValueError(f"coordinate '{time_dim}' missing in Dataset")
            if time_dim not in elevation_dims:
                raise ValueError(f"variable '{elevation_var}' has no '{time_dim}' dimension")

        if x_dim not in self._dataset.coords or y_dim not in self._dataset.coords:
            raise ValueError(f"coordinate(s) '{x_dim}' and/or '{y_dim}' missing in Dataset")

        if x_dim not in elevation_dims or y_dim not in elevation_dims:
            raise ValueError(f"variable '{elevation_var}' has no '{x_dim}' or '{y_dim}' dimension")

        self.elevation_var = elevation_var
        self.color_var = elevation_var
        self.x_dim = x_dim
        self.y_dim = y_dim

        self.time_dim = time_dim

        extra_dim_keys = elevation_dims - {x_dim, y_dim, time_dim}
        self._extra_dims = {dim: 0 for dim in extra_dim_keys}

        return self

    @property
    def data_vars(self) -> Dict[str, xr.DataArray]:
        if self._data_vars is None:
            dims = set(self._dataset[self.elevation_var].dims)
            self._data_vars = {
                k: var for k, var in self._dataset.data_vars.items() if set(var.dims) == dims
            }
        return self._data_vars

    @property
    def nsteps(self) -> int:
        if self.time_dim is not None:
            return len(self._dataset[self.time_dim])
        else:
            return 0

    def time_to_step(self, time):
        return self._dataset.indexes[self.time_dim].get_loc(time, method='nearest')

    @property
    def timestep(self) -> int:
        return self._timestep

    @timestep.setter
    def timestep(self, value: int):
        # need to update step view
        self._view_step = None

        self._timestep = value

    @property
    def current_time_fmt(self) -> str:
        return f'{self.timestep} / {self.view_step[self.time_dim].values}'

    @property
    def extra_dims(self) -> Dict[str, int]:
        return self._extra_dims

    def update_extra_dims(self, value: Dict[str, int]):
        # need to update both view and step view
        self._view = None
        self._view_step = None

        invalid_dims = tuple(set(value) - set(self._extra_dims))
        if invalid_dims:
            raise ValueError(f'invalid dimension(s): {invalid_dims}')

        self._extra_dims.update(value)

    @property
    def extra_dims_names(self) -> Dict[str, Tuple[str]]:
        names = {}

        for dim in self.extra_dims:
            idx = self._dataset.indexes.get(dim)

            if isinstance(idx, pd.MultiIndex):
                names[dim] = tuple(idx.names)
            else:
                names[dim] = (dim,)

        return names

    @property
    def extra_dims_sizes(self) -> Dict[str, int]:
        sizes = self._dataset[self.elevation_var].sizes

        return {dim: sizes[dim] for dim in self.extra_dims}

    @property
    def extra_dims_fmt(self) -> Dict[str, Tuple[str]]:
        fmt_values = {}

        for dim in self.extra_dims:
            da = self.view.get(dim)

            if da is None:
                fmt_values[dim] = ('',)
            else:
                value = da.values.item()

                if not isinstance(value, tuple):
                    value = (value,)

                fmt_values[dim] = tuple([str(v) for v in value])

        return fmt_values

    @property
    def view(self) -> xr.Dataset:
        """A slice view of the dataset at the selected extra dims positions."""
        if self._view is None:
            if len(self.extra_dims):
                self._view = self._dataset.isel(**self.extra_dims)
            else:
                self._view = self._dataset

        return self._view

    @property
    def view_step(self) -> xr.Dataset:
        """A slice view of the dataset at the current timestep."""
        if self._view_step is None:
            if self.time_dim is not None:
                self._view_step = self.view.isel(**{self.time_dim: self.timestep})
            else:
                self._view_step = self.view

        return self._view_step

    @property
    def elevation(self) -> xr.DataArray:
        return self._dataset[self.elevation_var]

    @property
    def color(self) -> xr.DataArray:
        return self._dataset[self.color_var]

    @property
    def current_elevation(self) -> xr.DataArray:
        return self.view_step[self.elevation_var]

    @property
    def current_color(self) -> xr.DataArray:
        return self.view_step[self.color_var]

    def to_unstructured_mesh(self) -> Tuple[np.ndarray, np.ndarray]:
        x = self._dataset[self.x_dim]
        y = self._dataset[self.y_dim]

        nr = len(y)
        nc = len(x)

        triangle_indices = np.empty((nr - 1, nc - 1, 2, 3), dtype='uint32')

        r = np.arange(nr * nc).reshape(nr, nc)

        triangle_indices[:, :, 0, 0] = r[:-1, :-1]
        triangle_indices[:, :, 1, 0] = r[:-1, 1:]
        triangle_indices[:, :, 0, 1] = r[:-1, 1:]

        triangle_indices[:, :, 1, 1] = r[1:, 1:]
        triangle_indices[:, :, :, 2] = r[1:, :-1, None]

        triangle_indices.shape = (-1, 3)

        xx, yy = np.meshgrid(x, y, sparse=True)

        vertices = np.empty((nr, nc, 3))
        vertices[:, :, 0] = xx
        vertices[:, :, 1] = yy
        vertices[:, :, 2] = np.zeros_like(xx)

        vertices = vertices.reshape(nr * nc, 3)

        return vertices, triangle_indices
