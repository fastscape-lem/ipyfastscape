import pytest
import xarray as xr

from ipyfastscape.common import (
    AppComponent,
    AppLinker,
    Coloring,
    DimensionExplorer,
    TimeStepper,
    VizApp,
)

from .utils import counter_callback


def test_app_component(dataset_init):

    with pytest.raises(NotImplementedError):
        AppComponent(dataset_init)

    class DummyAppComponent(AppComponent):
        def setup(self):
            return 'widget'

    component = DummyAppComponent(dataset_init)

    xr.testing.assert_identical(component.dataset, dataset_init)
    assert component.widget == 'widget'
    assert component.linkable_traits == []


def test_dimension_explorer(dataset_init):
    counter, clb = counter_callback()
    dim_explorer = DimensionExplorer(dataset_init, canvas_callback=clb)

    assert list(dim_explorer.sliders) == ['batch']
    assert dim_explorer.sliders['batch'].max == dataset_init.sizes['batch'] - 1
    assert dim_explorer.value_labels['batch'][0].value == '1'

    assert dim_explorer.linkable_traits == [(dim_explorer.sliders['batch'], 'value')]

    # test changing slider value
    dim_explorer.sliders['batch'].value = 1

    assert dim_explorer.value_labels['batch'][0].value == '2'
    xr.testing.assert_equal(dataset_init.isel(batch=1), dataset_init._widgets.view)
    assert counter['called'] == 1


def test_timestepper(dataset_init):
    counter, clb = counter_callback()
    timestepper = TimeStepper(dataset_init, canvas_callback=clb)

    nsteps = dataset_init.time.size

    assert timestepper.label.value == '0 / 0'
    assert timestepper.slider.max == nsteps - 1
    assert timestepper.play.max == nsteps - 1

    assert timestepper.linkable_traits == [
        (timestepper.slider, 'value'),
        (timestepper.play, 'value'),
        (timestepper.play_speed, 'value'),
    ]

    # test changing slider value
    timestepper.slider.value = 1

    assert dataset_init._widgets.timestep == 1
    assert timestepper.label.value == '1 / 100'
    assert counter['called'] == 1

    # test update play speed
    previous_interval = timestepper.play.interval
    timestepper.play_speed.value = timestepper.play_speed.max

    assert timestepper.play.interval != previous_interval

    # test extra methods
    timestepper.go_to_step(2)
    assert timestepper.slider.value == 2

    timestepper.go_to_time(99)
    assert timestepper.slider.value == 1


def test_coloring(dataset_init):
    counter_var, clb_var = counter_callback()
    counter_range, clb_range = counter_callback()

    coloring = Coloring(dataset_init, canvas_callback_var=clb_var, canvas_callback_range=clb_range)

    assert set(coloring.color_vars) == {'topography__elevation', 'other_var'}
    assert coloring.var_dropdown.value == 'topography__elevation'
    assert coloring.var_dropdown.options == coloring.color_vars

    assert coloring.min_input.value == dataset_init['topography__elevation'].min()
    assert coloring.max_input.value == dataset_init['topography__elevation'].max()

    # test changing dropdown
    coloring.var_dropdown.value = 'other_var'

    assert dataset_init._widgets.color_var == 'other_var'
    assert counter_var['called'] == 1
    assert counter_range['called'] == 1

    # test rescale buttons
    coloring.rescale_button.click()
    assert counter_range['called'] == 2

    coloring.rescale_step_button.click()
    assert counter_range['called'] == 3

    # test extra methods
    coloring.set_color_var('topography__elevation')
    assert coloring.var_dropdown.value == 'topography__elevation'

    with pytest.raises(ValueError, match='Invalid variable name.*'):
        coloring.set_color_var('not_a_var')

    coloring.set_color_limits(1, 2)
    assert coloring.min_input.value == 1
    assert coloring.max_input.value == 2


def test_viz_app_init(dataset):
    app = VizApp()
    assert app.dataset is None
    assert app.components == {}
    assert app.widget is app._output

    # check keyword arguments are passed to load_dataset
    app = VizApp(dataset, time_dim='time')
    assert app.dataset._widgets.time_dim == 'time'


def test_viz_app_load_dataset(dataset):
    app = VizApp()

    app.load_dataset(dataset, time_dim='time')

    xr.testing.assert_equal(app.dataset, dataset)
    assert app.dataset is not dataset  # must be a copy!

    assert 'timestepper' in app.components
    assert 'dimensions' in app.components

    with pytest.raises(TypeError, match='.*is not a xarray.Dataset object'):
        app.load_dataset('not_a_dataset')


def test_app_linker(dataset):
    app1 = VizApp(dataset, time_dim='time')
    app2 = VizApp(dataset, time_dim='time')

    linker = AppLinker([app1, app2], link_server=True)

    # test linked
    for b in linker.buttons:
        b.value = True

    app1.components['timestepper'].slider.value = 2
    assert app2.components['timestepper'].slider.value == 2

    app1.components['dimensions'].sliders['batch'].value = 1
    assert app2.components['dimensions'].sliders['batch'].value == 1

    # test unlinked
    for b in linker.buttons:
        b.value = False

    app1.components['timestepper'].slider.value = 0
    assert app2.components['timestepper'].slider.value != 0

    app1.components['dimensions'].sliders['batch'].value = 0
    assert app2.components['dimensions'].sliders['batch'].value != 0


def test_app_linker_error():
    with pytest.raises(TypeError, match='.*only accepts VizApp objects'):
        AppLinker([VizApp(), 'not_an_app'])

    with pytest.raises(ValueError, match='AppLinker works with at least two VizApp objects'):
        AppLinker([VizApp()])

    with pytest.raises(ValueError, match='AppLinker works with distinct VizApp objects'):
        app = VizApp()
        AppLinker([app, app])
