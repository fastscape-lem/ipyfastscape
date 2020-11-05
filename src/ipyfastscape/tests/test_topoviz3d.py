from ipyfastscape.topoviz3d import BackgroundColor, GanyScene, TopoViz3d, VerticalExaggeration

from .utils import counter_callback


def test_vertical_exaggeration(dataset):
    counter, clb = counter_callback()
    vert_exag = VerticalExaggeration(dataset, canvas_callback=clb)

    assert vert_exag.linkable_traits == [(vert_exag.slider, 'value')]

    # test change slider value
    vert_exag.slider.value = 10.0
    assert counter['called'] == 1

    # test extra methods
    vert_exag.set_factor(5.0)
    assert vert_exag.slider.value == 5.0


def test_background_color(dataset):
    bcolor = BackgroundColor(dataset)

    # test extra methods
    bcolor.set_color('black')
    assert bcolor.picker.value == 'black'


def test_gany_scene(dataset_init):
    gany_scene = GanyScene(dataset_init)

    assert gany_scene.isocolor.min == dataset_init['topography__elevation'].min()
    assert gany_scene.isocolor.max == dataset_init['topography__elevation'].max()

    assert gany_scene.linkable_traits == [
        (gany_scene.scene, 'camera_position'),
        (gany_scene.scene, 'camera_target'),
        (gany_scene.scene, 'camera_up'),
    ]


def test_topoviz3d(dataset):
    topoviz3d = TopoViz3d(dataset, time_dim='time')

    assert 'coloring' in topoviz3d.components
    assert 'vertical_exaggeration' in topoviz3d.components
    assert 'background_color' in topoviz3d.components

    topoviz3d.components['vertical_exaggeration'].set_factor(5.0)
    assert topoviz3d.components['canvas'].warp.factor == 5.0

    topoviz3d.components['coloring'].set_color_limits(10.0, 100.0)
    assert topoviz3d.components['canvas'].isocolor.min == 10.0
    assert topoviz3d.components['canvas'].isocolor.max == 100.0

    topoviz3d.components['coloring'].set_color_var('other_var')
    assert topoviz3d.components['canvas'].isocolor.min == dataset['other_var'].min()
    assert topoviz3d.components['canvas'].isocolor.max == dataset['other_var'].max()

    topoviz3d.components['background_color'].set_color('black')
    assert topoviz3d.canvas.background_color == 'black'
