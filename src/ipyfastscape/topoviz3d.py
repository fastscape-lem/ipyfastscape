from typing import Callable

import ipywidgets as widgets
from ipydatawidgets import NDArrayWidget
from ipygany import Component, IsoColor, PolyMesh, Scene, WarpByScalar

from .common import AppComponent, Coloring, VizApp
from .xr_accessor import WidgetsAccessor  # noqa: F401


class VerticalExaggeration(AppComponent):
    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
        self.slider = widgets.FloatSlider(value=1.0, min=0.0, max=20.0, step=0.1)
        self.slider.observe(self.canvas_callback, names='value')

        return widgets.VBox([widgets.Label('Vertical exaggeration:'), self.slider])


class BackgroundColor(AppComponent):
    def __init__(self, *args):
        super().__init__(*args)

    def setup(self):
        self.picker = widgets.ColorPicker(concise=True, value=self.canvas.background_color)

        widgets.jslink((self.picker, 'value'), (self.canvas, 'background_color'))

        return widgets.VBox([widgets.Label('Background color: '), self.picker])


class TopoViz3d(VizApp):

    canvas: Scene

    def _reset_canvas(self):
        vertices, triangle_indices = self.dataset._widgets.to_unstructured_mesh()

        elev_da = self.dataset._widgets.elevation
        elev_min = elev_da.min()
        elev_max = elev_da.max()

        self.warp_data = NDArrayWidget(self.dataset._widgets.current_elevation.values)
        self.color_data = NDArrayWidget(self.dataset._widgets.current_color.values)

        data = {
            'color': [Component(name='value', array=self.color_data, min=elev_min, max=elev_max)],
            'warp': [Component(name='value', array=self.warp_data, min=elev_min, max=elev_max)],
        }

        self.polymesh = PolyMesh(vertices=vertices, triangle_indices=triangle_indices, data=data)
        self.isocolor = IsoColor(
            self.polymesh, input=('color', 'value'), min=elev_min, max=elev_max
        )
        self.warp = WarpByScalar(self.isocolor, input='warp', factor=1)

        # TODO: remove this when ipygany supports listening to NDArrayWidget.array changes
        # see https://github.com/QuantStack/ipygany/issues/73
        widgets.dlink((self.warp_data, 'array'), (self.polymesh[('warp', 'value')], 'array'))
        widgets.dlink((self.color_data, 'array'), (self.polymesh[('color', 'value')], 'array'))

        self.canvas = Scene([self.warp])

    def _update_step(self):
        self.warp_data.array = self.dataset._widgets.current_elevation.values
        self.color_data.array = self.dataset._widgets.current_color.values

    def _update_scene_color_var(self):
        self.color_data.array = self.dataset._widgets.current_color

    def _update_scene_color_range(self, da):
        self.isocolor.min = da.min()
        self.isocolor.max = da.max()

    def _update_warp_factor(self, change):
        self.warp.factor = change['new']

    def _get_display_properties(self):
        props = {}

        coloring = Coloring(
            self.dataset,
            self.canvas,
            canvas_callback_var=self._update_scene_color_var,
            canvas_callback_range=self._update_scene_color_range,
        )
        widgets.jslink((coloring.min_input, 'value'), (self.isocolor, 'min'))
        widgets.jslink((coloring.max_input, 'value'), (self.isocolor, 'max'))
        props['coloring'] = coloring

        vert_exag = VerticalExaggeration(
            self.dataset, self.canvas, canvas_callback=self._update_warp_factor
        )
        props['vertical_exaggeration'] = vert_exag

        bcolor = BackgroundColor(self.dataset, self.canvas)
        props['background_color'] = bcolor

        return props
