from typing import Optional

import xarray as xr
from ipygany import Component, IsoColor, PolyMesh, Scene, WarpByScalar
from IPython.display import display
from ipywidgets import (
    Accordion,
    AppLayout,
    Button,
    ColorPicker,
    Dropdown,
    FloatSlider,
    FloatText,
    GridspecLayout,
    HBox,
    Label,
    Layout,
    Output,
    ToggleButton,
    VBox,
    jslink,
)

from .common import TimeStepper
from .xr_accessor import WidgetsAccessor  # noqa: F401


class TopoViz3d:
    def __init__(self, *args, height=600, **kwargs):

        self._default_background_color = '#969BAA'
        self._scene_height = int(height)
        self.scene = Scene([], background_color=self._default_background_color)

        self.output = Output()
        self.output.layout = Layout(
            height=str(self._scene_height + 10 + 30) + 'px',
        )

        self.timestepper = None

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

        self._reset_gui()

    def _reset_scene(self):
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

        self.scene = Scene([self.warp], background_color=self._default_background_color)

    def _update_scene_data_slice(self, _):
        new_warp_array = self.dataset._widgets.current_elevation.values
        self.polymesh[('warp', 'value')].array = new_warp_array

        new_color_array = self.dataset._widgets.current_color.values
        self.polymesh[('color', 'value')].array = new_color_array

    def _get_coloring_widgets(self):
        da = self.dataset._widgets.color

        clr_min_input = FloatText(value=da.min(), layout=Layout(height='auto', width='auto'))
        clr_max_input = FloatText(value=da.max(), layout=Layout(height='auto', width='auto'))

        jslink((clr_min_input, 'value'), (self.isocolor, 'min'))
        jslink((clr_max_input, 'value'), (self.isocolor, 'max'))

        def update_coloring_range(step=False):
            if step:
                da = self.dataset._widgets.current_color
            else:
                da = self.dataset._widgets.color

            self.isocolor.min = da.min()
            self.isocolor.max = da.max()

        rescale_button = Button(
            description='Rescale',
            tooltip='Rescale to actual data range',
            layout=Layout(height='auto', width='auto'),
        )
        rescale_button.on_click(lambda _: update_coloring_range())

        rescale_button_step = Button(
            description='Rescale Step',
            tooltip='Rescale to actual data range (current step only)',
            layout=Layout(height='auto', width='auto'),
        )
        rescale_button_step.on_click(lambda _: update_coloring_range(step=True))

        range_grid = GridspecLayout(2, 2)
        range_grid[0, 0] = clr_min_input
        range_grid[0, 1] = clr_max_input
        range_grid[1, 0] = rescale_button
        if self.dataset._widgets.time_dim is not None:
            range_grid[1, 1] = rescale_button_step

        def change_coloring_var(change):
            self.dataset._widgets.color_var = change['new']

            with self.scene.hold_sync():
                self.polymesh[('color', 'value')].array = self.dataset._widgets.current_color
                update_coloring_range()

        if len(self.dataset):
            coloring_dropdown = Dropdown(
                value=self.dataset._widgets.elevation_var,
                options=list(self.dataset._widgets.data_vars),
            )
        else:
            coloring_dropdown = Dropdown(options=[])

        coloring_dropdown.observe(change_coloring_var, names='value')

        return [
            VBox([Label('Coloring:'), coloring_dropdown]),
            VBox([Label('Color range:'), range_grid]),
        ]

    def _get_vertical_exaggeration_widget(self):
        def update_warp(change):
            self.warp.factor = change['new']

        warp_slider = FloatSlider(value=self.warp.factor, min=0.0, max=20.0, step=0.1)
        warp_slider.observe(update_warp, names='value')

        return VBox([Label('Vertical exaggeration:'), warp_slider])

    def _get_background_color_widget(self):
        clr_pick = ColorPicker(concise=True, value=self.scene.background_color)

        jslink((clr_pick, 'value'), (self.scene, 'background_color'))

        return VBox([Label('Background color: '), clr_pick])

    def _get_properties_widgets(self):
        return self._get_coloring_widgets() + [
            self._get_vertical_exaggeration_widget(),
            self._get_background_color_widget(),
        ]

    def _reset_gui(self):
        self.output.clear_output()

        self._reset_scene()
        self.scene.layout = Layout(
            width='100%', height=str(self._scene_height) + 'px', overflow='hidden'
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

        if self.dataset._widgets.time_dim is not None:
            self.timestepper = TimeStepper(self.dataset, self._update_scene_data_slice)
            header_elements.append(self.timestepper.get_widget())

        properties = VBox(self._get_properties_widgets())

        left_pane = Accordion([properties])
        left_pane.set_title(0, 'Display properties')
        left_pane.layout = Layout(
            width='400px',
            height='95%',
            margin='0 10px 0 0',
            flex='0 0 auto',
        )

        gui = AppLayout(
            header=HBox(header_elements),
            left_sidebar=None,
            right_sidebar=None,
            center=HBox([left_pane, self.scene]),
            footer=None,
            pane_heights=['30px', 3, 0],
            grid_gap='10px',
            width='100%',
            overflow='hidden',
        )

        def scene_resize():
            # TODO: ipygany proper scene canvas resizing
            # the workaround below is a hack (force change with before back to 100%)
            with self.scene.hold_sync():
                self.scene.layout.width = 'auto'
                self.scene.layout.width = '100%'

        def toggle_left_pane(change):
            if change['new']:
                left_pane.layout.display = 'block'
                scene_resize()
            else:
                left_pane.layout.display = 'none'
                scene_resize()

        menu_button.observe(toggle_left_pane, names='value')

        with self.output:
            display(gui)

    def show(self):
        display(self.output)
