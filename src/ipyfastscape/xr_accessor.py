import numpy as np
import xarray as xr


@xr.register_dataset_accessor('_widgets')
class WidgetsAccessor:
    """Internal xarray.Dataset extension that stores extra state + implement some
    useful methods for interacting with widgets.

    """

    def __init__(self, dataset):
        self._dataset = dataset

        self._data_vars = None
        self._current_slice = None

        self._timestep = 0
        self._nsteps = None

    def __call__(self, x='x', y='y', time=None, elevation_var='topography__elevation'):

        if elevation_var not in self._dataset:
            raise ValueError(f"variable '{elevation_var}' not found in Dataset")

        elevation_da = self._dataset[elevation_var]
        elevation_dims = set(elevation_da.dims)

        if time is not None:
            if time not in self._dataset.coords:
                raise ValueError(f"coordinate '{time}' not found in Dataset")
            if time not in elevation_dims:
                raise ValueError(f"variable '{elevation_var}' has no '{time}' dimension")

        if x not in self._dataset.coords or y not in self._dataset.coords:
            raise ValueError(f"coordinate(s) '{x}' and/or '{y}' missing in Dataset")

        if x not in elevation_dims or y not in elevation_dims:
            raise ValueError(f"variable '{elevation_var}' has no '{x}' or '{y}' dimension")

        self.elevation_var = elevation_var
        self.color_var = elevation_var
        self.x_dim = x
        self.y_dim = y

        self.time_dim = time

        return self

    @property
    def data_vars(self):
        if self._data_vars is None:
            dims = set(self._dataset[self.elevation_var].dims)
            self._data_vars = {
                k: var for k, var in self._dataset.data_vars.items() if set(var.dims) == dims
            }
        return self._data_vars

    @property
    def nsteps(self):
        if self._nsteps is None:
            if self.time_dim is not None:
                self._nsteps = len(self._dataset[self.time_dim])
            else:
                self._nsteps = 0

        return self._nsteps

    @property
    def timestep(self):
        return self._timestep

    @timestep.setter
    def timestep(self, value):
        # remove current slice from cache
        self._current_slice = None

        self._timestep = value

    @property
    def current_time_str(self):
        return f'{self.timestep} / {self.current_slice[self.time_dim].values}'

    @property
    def current_slice(self):
        if self._current_slice is None:
            sel_dict = {}

            if self.time_dim is not None:
                sel_dict[self.time_dim] = self._timestep

            self._current_slice = self._dataset.isel(**sel_dict)

        return self._current_slice

    @property
    def elevation(self):
        return self._dataset[self.elevation_var]

    @property
    def color(self):
        return self._dataset[self.color_var]

    @property
    def current_elevation(self):
        return self.current_slice[self.elevation_var]

    @property
    def current_color(self):
        return self.current_slice[self.color_var]

    def to_unstructured_mesh(self):
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
