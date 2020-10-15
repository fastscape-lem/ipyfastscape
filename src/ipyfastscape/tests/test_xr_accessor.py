import pytest


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
