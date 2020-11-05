import numpy as np
import pytest
import xarray as xr


def test_initializer(dataset):
    dataset._widgets(time_dim='time')

    assert dataset._widgets.elevation_var == 'topography__elevation'
    assert dataset._widgets.color_var == 'topography__elevation'
    assert dataset._widgets.x_dim == 'x'
    assert dataset._widgets.y_dim == 'y'
    assert dataset._widgets.time_dim == 'time'
    assert dataset._widgets.extra_dims == {'batch': 0}


def test_initializer_no_time_dim(dataset):
    # assert 'time' is considered as an extra dimension
    dataset._widgets(time_dim=None)

    assert dataset._widgets.extra_dims == {'batch': 0, 'time': 0}


def test_initializer_error(dataset):

    ds = dataset.drop_vars('topography__elevation')

    with pytest.raises(ValueError, match=r'variable.*not found in Dataset'):
        ds._widgets()

    for cname in ['time', 'x', 'y']:
        ds = dataset.drop_vars(cname)

        with pytest.raises(ValueError, match=r'coordinate.*missing in Dataset'):
            ds._widgets(time_dim='time')

        ds = dataset.isel(**{cname: 0}).squeeze()

        with pytest.raises(ValueError, match=r'variable.*has no.*dimension'):
            ds._widgets(time_dim='time')


def test_data_vars(dataset_init):

    assert 'topography__elevation' in dataset_init._widgets.data_vars
    assert 'other_var' in dataset_init._widgets.data_vars
    assert 'xy_var' not in dataset_init._widgets.data_vars


@pytest.mark.parametrize('time_dim, expected_nsteps', [(None, 0), ('time', 3)])
def test_nsteps(dataset, time_dim, expected_nsteps):
    ds = dataset.copy()
    ds._widgets(time_dim=time_dim)
    assert ds._widgets.nsteps == expected_nsteps


def test_time_to_step(dataset_init):
    assert dataset_init._widgets.time_to_step(101) == 1


def test_timestep(dataset_init):
    assert dataset_init._widgets.timestep == 0

    dataset_init._widgets.timestep = 1
    assert dataset_init._widgets.timestep == 1


def test_current_time_fmt(dataset_init):
    dataset_init._widgets.timestep = 1
    assert dataset_init._widgets.current_time_fmt == '1 / 100'


def test_extra_dims(dataset_init):
    assert dataset_init._widgets.extra_dims == {'batch': 0}


def test_update_extra_dims(dataset_init):
    dataset_init._widgets.update_extra_dims({'batch': 1})
    assert dataset_init._widgets.extra_dims == {'batch': 1}

    with pytest.raises(ValueError, match='invalid dimension.*'):
        dataset_init._widgets.update_extra_dims({'invalid_dim': 0})


def test_extra_dims_names(dataset_init):
    assert dataset_init._widgets.extra_dims_names == {'batch': ('batch',)}

    ds = dataset_init.assign(batch_level2=('batch', ['a', 'b', 'c'])).set_index(
        midx=['batch', 'batch_level2']
    )

    expected = {'midx': ('batch', 'batch_level2')}
    assert ds._widgets(time_dim='time').extra_dims_names == expected


def test_extra_dims_sizes(dataset_init):
    assert dataset_init._widgets.extra_dims_sizes == {'batch': 3}


def test_extra_dims_fmt(dataset_init):
    assert dataset_init._widgets.extra_dims_fmt == {'batch': ('1',)}

    ds = dataset_init.assign(batch_level2=('batch', ['a', 'b', 'c'])).set_index(
        midx=['batch', 'batch_level2']
    )

    assert ds._widgets(time_dim='time').extra_dims_fmt == {'midx': ('1', 'a')}

    ds2 = ds.reset_index('midx', drop=True)

    assert ds2._widgets(time_dim='time').extra_dims_fmt == {'midx': ('',)}


def test_view(dataset_init):
    xr.testing.assert_equal(dataset_init.isel(batch=0), dataset_init._widgets.view)

    # no extra dims
    ds = dataset_init.isel(batch=0).squeeze()
    ds._widgets(time_dim='time')
    xr.testing.assert_equal(ds, ds._widgets.view)

    # check view is updated
    dataset_init._widgets.update_extra_dims({'batch': 1})
    xr.testing.assert_equal(dataset_init.isel(batch=1), dataset_init._widgets.view)


def test_view_step(dataset_init):
    xr.testing.assert_equal(dataset_init.isel(batch=0, time=0), dataset_init._widgets.view_step)

    # no time dim
    ds = dataset_init.isel(time=0).squeeze()
    ds._widgets()
    xr.testing.assert_equal(ds.isel(batch=0), ds._widgets.view_step)

    # check view is updated
    dataset_init._widgets.update_extra_dims({'batch': 1})
    xr.testing.assert_equal(dataset_init.isel(batch=1, time=0), dataset_init._widgets.view_step)

    dataset_init._widgets.timestep = 1
    xr.testing.assert_equal(dataset_init.isel(batch=1, time=1), dataset_init._widgets.view_step)


def test_var_properties(dataset_init):
    xr.testing.assert_equal(
        dataset_init._widgets.elevation, dataset_init[dataset_init._widgets.elevation_var]
    )

    xr.testing.assert_equal(
        dataset_init._widgets.color, dataset_init[dataset_init._widgets.color_var]
    )

    xr.testing.assert_equal(
        dataset_init._widgets.current_elevation,
        dataset_init._widgets.view_step[dataset_init._widgets.elevation_var],
    )

    xr.testing.assert_equal(
        dataset_init._widgets.current_color,
        dataset_init._widgets.view_step[dataset_init._widgets.color_var],
    )


def test_to_unstructured_mesh(dataset_init):
    vertices, triangles = dataset_init._widgets.to_unstructured_mesh()

    assert vertices.shape == (len(dataset_init.x) * len(dataset_init.y), 3)
    np.testing.assert_equal(vertices[:, 2], 0)

    assert triangles.shape == (len(dataset_init.x) * len(dataset_init.y) - 1, 3)
