from typing import Callable

from ipygany import Component, IsoColor, PolyMesh, Scene, WarpByScalar
from ipywidgets import ColorPicker, FloatSlider, Label, VBox, jslink

from .common import AppComponent, Coloring, VizApp
from .xr_accessor import WidgetsAccessor  # noqa: F401


class VerticalExaggeration(AppComponent):
    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
        self.slider = FloatSlider(value=1.0, min=0.0, max=20.0, step=0.1)
        self.slider.observe(self.canvas_callback, names='value')

        return VBox([Label('Vertical exaggeration:'), self.slider])


class BackgroundColor(AppComponent):
    def __init__(self, *args):
        super().__init__(*args)

    def setup(self):
        self.picker = ColorPicker(concise=True, value=self.canvas.background_color)

        jslink((self.picker, 'value'), (self.canvas, 'background_color'))

        return VBox([Label('Background color: '), self.picker])


class TopoViz3d(VizApp):
    def _reset_canvas(self):
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

        self.canvas = Scene([self.warp])

    def _update_step(self):
        new_warp_array = self.dataset._widgets.current_elevation.values
        self.polymesh[('warp', 'value')].array = new_warp_array

        new_color_array = self.dataset._widgets.current_color.values
        self.polymesh[('color', 'value')].array = new_color_array

    def _update_scene_color_var(self):
        self.polymesh[('color', 'value')].array = self.dataset._widgets.current_color

    def _update_scene_color_range(self, da):
        self.isocolor.min = da.min()
        self.isocolor.max = da.max()

    def _update_warp_factor(self, change):
        self.warp.factor = change['new']

    def _reset_display_properties(self):
        props = {}

        coloring = Coloring(
            self.dataset,
            self.canvas,
            canvas_callback_var=self._update_scene_color_var,
            canvas_callback_range=self._update_scene_color_range,
        )
        jslink((coloring.min_input, 'value'), (self.isocolor, 'min'))
        jslink((coloring.max_input, 'value'), (self.isocolor, 'max'))
        props['coloring'] = coloring

        vert_exag = VerticalExaggeration(
            self.dataset, self.canvas, canvas_callback=self._update_warp_factor
        )
        props['vertical_exaggeration'] = vert_exag

        bcolor = BackgroundColor(self.dataset, self.canvas)
        props['background_color'] = bcolor

        self.display_properties = props
