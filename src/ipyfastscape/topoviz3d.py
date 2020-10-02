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

    def _normalize_dataset(self, dataset: xr.Dataset) -> xr.Dataset:
        if not isinstance(dataset, xr.Dataset):
            raise TypeError(f'{dataset} is not a xarray.Dataset object')

        if self.elevation_var not in dataset:
            raise ValueError(f"variable '{self.elevation_var}' not found in Dataset")

        elevation_da = dataset[self.elevation_var]
        elevation_dims = set(elevation_da.dims)

        if self.time is not None:
            if self.time not in dataset.coords:
                raise ValueError(f"coordinate '{self.time}' not found in Dataset")
            if self.time not in elevation_dims:
                raise ValueError(f"variable '{self.elevation_var}' has no '{self.time}' dimension")

        if self.x_dim not in dataset.coords or self.y_dim not in dataset.coords:
            raise ValueError(
                f"coordinate(s) '{self.x_dim}' and/or '{self.y_dim}' missing in Dataset"
            )

        if self.x_dim not in elevation_dims or self.y_dim not in elevation_dims:
            raise ValueError(
                f"variable '{self.elevation_var}' has no '{self.x_dim}' or '{self.y_dim}' dimension"
            )

        selected_vars = [
            vname for vname, var in dataset.data_vars.items() if set(var.dims) == elevation_dims
        ]

        return dataset[selected_vars]

    def load_dataset(
        self,
        dataset: xr.Dataset,
        x: str = 'x',
        y: str = 'y',
        elevation_var: str = 'topography__elevation',
        time: Optional[str] = None,
    ):
        self.x_dim = x
        self.y_dim = y
        self.elevation_var = elevation_var
        self.color_var = elevation_var
        self.time = time
        self.timestep = 0

        self.dataset = self._normalize_dataset(dataset)
        self._reset_gui()

    def _get_mesh_geometry(self):
        x = self.dataset[self.x_dim]
        y = self.dataset[self.y_dim]

        nr = len(y)
        nc = len(x)

        triangle_indices = np.empty((nr - 1, nc - 1, 2, 3), dtype='uint32')

        r = np.arange(nr * nc).reshape(nr, nc)

        triangle_indices[:, :, 0, 0] = r[:-1, :-1]
        triangle_indices[:, :, 1, 0] = r[:-1, 1:]
        triangle_indices[:, :, 0, 1] = r[:-1, 1:]

        triangle_indices[:, :, 1, 1] = r[1:, 1:]
        triangle_indices[:, :, :, 2] = r[1:, :-1, None]

        triangle_indices.shape = (-1, 3)

        xx, yy = np.meshgrid(x, y, sparse=True)

        vertices = np.empty((nr, nc, 3))
        vertices[:, :, 0] = xx
        vertices[:, :, 1] = yy
        vertices[:, :, 2] = np.zeros_like(xx)

        vertices = vertices.reshape(nr * nc, 3)

        return vertices, triangle_indices

    def _reset_scene(self):
        if not len(self.dataset):
            return

        vertices, triangle_indices = self._get_mesh_geometry()

        elev_da = self.dataset[self.elevation_var]
        elev_min = elev_da.min()
        elev_max = elev_da.max()

        if self.time is None:
            elev_arr = elev_da.values
        else:
            elev_arr = elev_da.isel(**{self.time: 0}).values

        data = {
            'color': [Component(name='value', array=elev_arr, min=elev_min, max=elev_max)],
            'warp': [Component(name='value', array=elev_arr, min=elev_min, max=elev_max)],
        }

        self.color_var = self.elevation_var

        self.polymesh = PolyMesh(vertices=vertices, triangle_indices=triangle_indices, data=data)
        self.isocolor = IsoColor(
            self.polymesh, input=('color', 'value'), min=elev_min, max=elev_max
        )
        self.warp = WarpByScalar(self.isocolor, input='warp', factor=1)

        self.scene = Scene([self.warp], background_color=self._default_background_color)

    def _get_timestep_widgets(self):
        nsteps = len(self.dataset[self.time])
        time_val0 = self.dataset[self.time].values[0]

        timestep_label = Label(f'0 / {time_val0}')
        timestep_label.layout = Layout(width='150px')

        def update_time(change):
            self.timestep = change['new']
            ds_step = self.dataset.isel(**{self.time: self.timestep})
            time_val = self.dataset[self.time].values[self.timestep]

            timestep_label.value = f'{self.timestep} / {time_val}'
            self.polymesh[('warp', 'value')].array = ds_step[self.elevation_var].values
            self.polymesh[('color', 'value')].array = ds_step[self.color_var].values

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
        elev_da = self.dataset[self.color_var]

        clr_min_input = FloatText(value=elev_da.min(), layout=Layout(height='auto', width='auto'))
        clr_max_input = FloatText(value=elev_da.max(), layout=Layout(height='auto', width='auto'))

        jslink((clr_min_input, 'value'), (self.isocolor, 'min'))
        jslink((clr_max_input, 'value'), (self.isocolor, 'max'))

        def update_coloring_range(step=False):
            da = self.dataset[self.color_var]

            if step:
                da = da.isel(**{self.time: self.timestep})

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
        if self.time is not None:
            range_grid[1, 1] = rescale_button_step

        def change_coloring_var(change):
            self.color_var = change['new']
            new_da = self.dataset[self.color_var]

            if self.time is None:
                new_arr = new_da.values
            else:
                new_arr = new_da.isel(**{self.time: self.timestep}).values

            with self.scene.hold_sync():
                self.polymesh[('color', 'value')].array = new_arr
                update_coloring_range()

        if len(self.dataset):
            coloring_dropdown = Dropdown(
                value=self.elevation_var, options=list(self.dataset.data_vars)
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

        if self.time is not None:
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
