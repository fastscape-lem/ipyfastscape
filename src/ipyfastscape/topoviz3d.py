from typing import Optional

import numpy as np
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
    IntSlider,
    Label,
    Layout,
    Output,
    Play,
    VBox,
    jslink,
)

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

    def _get_timestep_widgets(self):
        nsteps = self.dataset._widgets.nsteps

        timestep_label = Label(self.dataset._widgets.current_time_str)
        timestep_label.layout = Layout(width='150px')

        def update_time(change):
            self.dataset._widgets.timestep = change['new']

            timestep_label.value = self.dataset._widgets.current_time_str
            self.polymesh[('warp', 'value')].array = self.dataset._widgets.current_elevation.values
            self.polymesh[('color', 'value')].array = self.dataset._widgets.current_color.values

        timestep_slider = IntSlider(value=0, min=0, max=nsteps - 1, readout=False)
        timestep_slider.observe(update_time, names='value')
        timestep_slider.layout = Layout(width='auto', flex='3 1 0%')

        timestep_play = Play(value=0, min=0, max=nsteps - 1, interval=100)

        def update_speed(change):
            speed_ms = int((520 + 500 * np.cos(change['new'] * np.pi / 50)) / 2)
            timestep_play.interval = speed_ms

        play_speed = IntSlider(value=30, min=0, max=50, readout=False)
        play_speed.observe(update_speed, names='value')
        play_speed.layout = Layout(width='auto', flex='1 1 0%')

        jslink((timestep_play, 'value'), (timestep_slider, 'value'))

        timestep_box = HBox(
            [
                timestep_play,
                Label('slow/fast: '),
                play_speed,
                Label('steps: '),
                timestep_slider,
                timestep_label,
            ]
        )
        timestep_box.layout = Layout(width='100%')

        return timestep_box

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
            tootip='Rescale to actual data range',
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
            width='auto', height=str(self._scene_height) + 'px', overflow='hidden'
        )

        if self.dataset._widgets.time_dim is not None:
            timesteps = self._get_timestep_widgets()
            timesteps.layout = Layout(margin='0 0 0 400px')
        else:
            timesteps = None

        properties = VBox(self._get_properties_widgets())

        left_pane = Accordion([properties])
        left_pane.set_title(0, 'Display properties')
        left_pane.layout = Layout(width='auto', height='95%')

        gui = AppLayout(
            header=timesteps,
            left_sidebar=left_pane,
            right_sidebar=self.scene,
            center=None,
            footer=None,
            pane_widths=['400px', 0, 3],
            pane_heights=['30px', 3, 0],
            grid_gap='10px',
            width='100%',
            overflow='hidden',
        )

        with self.output:
            display(gui)

    def show(self):
        display(self.output)
