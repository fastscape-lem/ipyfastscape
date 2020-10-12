from typing import Callable

import ipywidgets as widgets
from ipygany import Component, IsoColor, PolyMesh, Scene, WarpByScalar

from .common import AppComponent, Coloring, VizApp
from .xr_accessor import WidgetsAccessor  # noqa: F401


class VerticalExaggeration(AppComponent):
    allow_link = False
    name = 'Vert. Exaggeration'

    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
        self.slider = widgets.FloatSlider(value=1.0, min=0.0, max=20.0, step=0.1)
        self.slider.observe(self.canvas_callback, names='value')

        return widgets.VBox([widgets.Label('Vertical exaggeration:'), self.slider])

    @property
    def linkable_traits(self):
        return [(self.slider, 'value')]

    def set_factor(self, value):
        self.slider.value = value


class BackgroundColor(AppComponent):
    allow_link = False
    name = 'Background Color'

    def setup(self):
        self.picker = widgets.ColorPicker(concise=True, value='white')

        return widgets.VBox([widgets.Label('Background color: '), self.picker])

    def set_color(self, value):
        self.picker.value = value


class GanyScene(AppComponent):
    name = '3D Scene'

    def setup(self):
        vertices, triangle_indices = self.dataset._widgets.to_unstructured_mesh()

        elev_da = self.dataset._widgets.elevation
        elev_min = elev_da.min()
        elev_max = elev_da.max()
        elev_arr = self.dataset._widgets.current_elevation.values

        data = {
            'color': [Component(name='value', array=elev_arr, min=elev_min, max=elev_max)],
            'warp': [Component(name='value', array=elev_arr, min=elev_min, max=elev_max)],
        }

        self.polymesh = PolyMesh(vertices=vertices, triangle_indices=triangle_indices, data=data)
        self.isocolor = IsoColor(
            self.polymesh, input=('color', 'value'), min=elev_min, max=elev_max
        )
        self.warp = WarpByScalar(self.isocolor, input='warp', factor=1)
        self.scene = Scene([self.warp])

        return self.scene

    def redraw_color_warp(self):
        new_warp_array = self.dataset._widgets.current_elevation.values
        new_color_array = self.dataset._widgets.current_color.values

        with self.scene.hold_sync():
            self.polymesh[('color', 'value')].array = new_color_array
            self.polymesh[('warp', 'value')].array = new_warp_array

    def reset_color_range(self, step=False):
        if step:
            da = self.dataset._widgets.current_color
        else:
            da = self.dataset._widgets.color

        with self.scene.hold_sync():
            self.isocolor.min = da.min()
            self.isocolor.max = da.max()

    def linkable_traits(self):
        # TODO: jslink camera doesn't work yet in ipygany
        return [
            (self.scene, 'camera_position'),
            (self.scene, 'camera_target'),
            (self.scene, 'camera_up'),
        ]


class TopoViz3d(VizApp):
    def _update_warp_factor(self, change):
        self.components['canvas'].warp.factor = change['new']

    def _reset_canvas(self):
        gs = GanyScene(self.dataset)
        self._canvas = gs.scene

        return gs

    def _redraw_canvas(self):
        self.components['canvas'].redraw_color_warp()

    def _get_display_properties(self):
        props = {}

        coloring = Coloring(
            self.dataset,
            canvas_callback_var=self.components['canvas'].redraw_color_warp,
            canvas_callback_range=self.components['canvas'].reset_color_range,
        )
        widgets.jslink((coloring.min_input, 'value'), (self.components['canvas'].isocolor, 'min'))
        widgets.jslink((coloring.max_input, 'value'), (self.components['canvas'].isocolor, 'max'))
        props['coloring'] = coloring

        vert_exag = VerticalExaggeration(self.dataset, canvas_callback=self._update_warp_factor)
        props['vertical_exaggeration'] = vert_exag

        bgcolor = BackgroundColor(self.dataset)
        widgets.jslink((bgcolor.picker, 'value'), (self.canvas, 'background_color'))
        props['background_color'] = bgcolor

        return props
