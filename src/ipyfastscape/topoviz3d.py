from typing import List, Optional, Tuple

import xarray as xr
from ipygany import Component, IsoColor, PolyMesh, Scene, WarpByScalar
from IPython.display import display
from ipywidgets import (
    Accordion,
    AppLayout,
    ColorPicker,
    FloatSlider,
    HBox,
    Label,
    Layout,
    Output,
    ToggleButton,
    VBox,
    jslink,
)

from .common import Coloring, TimeStepper
from .xr_accessor import WidgetsAccessor  # noqa: F401


class TopoViz3d:
    def __init__(self, *args, canvas_height=600, **kwargs):

        self._canvas_height = int(canvas_height)
        # add grid gap + app header
        self._output_height = self._canvas_height + 10 + 30
        self._default_background_color = '#969BAA'
        self.canvas = Scene([], background_color=self._default_background_color)

        self.output = Output()
        self.output.layout = Layout(height=str(self._output_height) + 'px')

        self.timestepper = None
        self.coloring = None

        if len(args) == 1:
            self.load_dataset(args[0], **kwargs)
        elif len(args) > 1:
            raise ValueError(
                'too many arguments given to `TopoViz3d.__init__`, which accepts one xarray.Dataset'
            )

    def load_dataset(
        self,
        dataset: xr.Dataset,
        x: str = 'x',
        y: str = 'y',
        elevation_var: str = 'topography__elevation',
        time: Optional[str] = None,
    ):
        if not isinstance(dataset, xr.Dataset):
            raise TypeError(f'{dataset} is not a xarray.Dataset object')

        # shallow copy of dataset to support multiple Viz instances from the same dataset
        self.dataset = dataset.copy()
        self.dataset._widgets(x=x, y=y, elevation_var=elevation_var, time=time)

        self.reset_app()

    def reset_canvas(self):
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

        self.canvas = Scene([self.warp], background_color=self._default_background_color)

    def _update_scene_data_slice(self):
        new_warp_array = self.dataset._widgets.current_elevation.values
        self.polymesh[('warp', 'value')].array = new_warp_array

        new_color_array = self.dataset._widgets.current_color.values
        self.polymesh[('color', 'value')].array = new_color_array

    def _update_scene_color_var(self):
        self.polymesh[('color', 'value')].array = self.dataset._widgets.current_color

    def _update_scene_color_range(self, da):
        self.isocolor.min = da.min()
        self.isocolor.max = da.max()

    @property
    def links(self) -> List[Tuple[Tuple, Tuple]]:
        return [
            ((self.coloring.min_input, 'value'), (self.isocolor, 'min')),
            ((self.coloring.max_input, 'value'), (self.isocolor, 'max')),
        ]

    def _get_vertical_exaggeration_widget(self):
        def update_warp(change):
            self.warp.factor = change['new']

        warp_slider = FloatSlider(value=self.warp.factor, min=0.0, max=20.0, step=0.1)
        warp_slider.observe(update_warp, names='value')

        return VBox([Label('Vertical exaggeration:'), warp_slider])

    def _get_background_color_widget(self):
        clr_pick = ColorPicker(concise=True, value=self.canvas.background_color)

        jslink((clr_pick, 'value'), (self.canvas, 'background_color'))

        return VBox([Label('Background color: '), clr_pick])

    def _get_properties_widgets(self):
        return [
            self._get_vertical_exaggeration_widget(),
            self._get_background_color_widget(),
        ]

    def reset_app(self):
        self.output.clear_output()

        self.reset_canvas()
        self.canvas.layout = Layout(
            width='100%', height=str(self._canvas_height) + 'px', overflow='hidden'
        )

        # header
        header_elements = []

        menu_button = ToggleButton(
            value=True,
            tooltip='Show/Hide sidebar',
            icon='bars',
            layout=Layout(width='50px', height='auto', margin='0 10px 0 0'),
        )

        header_elements.append(menu_button)

        # left pane
        if self.dataset._widgets.time_dim is not None:
            self.timestepper = TimeStepper(self.dataset, self.canvas, self._update_scene_data_slice)
            header_elements.append(self.timestepper.widget)

        self.coloring = Coloring(
            self.dataset, self.canvas, self._update_scene_color_var, self._update_scene_color_range
        )

        properties_elements = [
            self.coloring.widget,
            self._get_vertical_exaggeration_widget(),
            self._get_background_color_widget(),
        ]
        properties = VBox(properties_elements)

        left_pane = Accordion([properties])
        left_pane.set_title(0, 'Display properties')
        left_pane.layout = Layout(
            width='400px',
            height='95%',
            margin='0 10px 0 0',
            flex='0 0 auto',
        )

        # app
        app = AppLayout(
            header=HBox(header_elements),
            left_sidebar=None,
            right_sidebar=None,
            center=HBox([left_pane, self.canvas]),
            footer=None,
            pane_heights=['30px', 3, 0],
            grid_gap='10px',
            width='100%',
            overflow='hidden',
        )

        def scene_resize():
            # TODO: ipygany proper scene canvas resizing
            # the workaround below is a hack (force change with before back to 100%)
            with self.canvas.hold_sync():
                self.canvas.layout.width = 'auto'
                self.canvas.layout.width = '100%'

        def toggle_left_pane(change):
            if change['new']:
                left_pane.layout.display = 'block'
                scene_resize()
            else:
                left_pane.layout.display = 'none'
                scene_resize()

        menu_button.observe(toggle_left_pane, names='value')

        for widgets in self.links:
            jslink(*widgets)

        with self.output:
            display(app)

    def show(self):
        display(self.output)
