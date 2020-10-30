import numpy as np
import pytest
import xarray as xr

from ipyfastscape.xr_accessor import WidgetsAccessor  # noqa: F401


@pytest.fixture
def dataset() -> xr.Dataset:
    x = np.array([0, 1, 2])
    y = np.array([0, 1, 2])
    time = np.array([0, 100, 200])
    batch = np.array([1, 2, 3])

    elevation = (
        batch[:, None, None, None]
        * time[None, :, None, None]
        * y[None, None, :, None]
        * x[None, None, None, :]
    )
    other_var = np.ones_like(elevation)
    xy_var = x[None, :] * y[:, None]

    ds = xr.Dataset(
        data_vars={
            'topography__elevation': (('batch', 'time', 'y', 'x'), elevation),
            'other_var': (('batch', 'time', 'y', 'x'), other_var),
            'xy_var': (('y', 'x'), xy_var),
        },
        coords={'batch': batch, 'time': time, 'y': y, 'x': x},
    )

    return ds


@pytest.fixture
def dataset_init(dataset) -> xr.Dataset:
    dataset._widgets(time_dim='time')

    return dataset
