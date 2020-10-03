import math
from typing import Any, Callable

import xarray as xr
from ipywidgets import (
    Button,
    Dropdown,
    FloatText,
    GridspecLayout,
    HBox,
    IntSlider,
    Label,
    Layout,
    Play,
    VBox,
    jslink,
)

from .xr_accessor import WidgetsAccessor  # noqa: F401


class IpyFastscapeWidget:
    def __init__(self, dataset: xr.Dataset, canvas: Any):
        self.dataset = dataset
        self.canvas = canvas
        self._widget = None

    @property
    def widget(self):
        return self._widget


class TimeStepper(IpyFastscapeWidget):
    def __init__(self, dataset: xr.Dataset, canvas: Any, update_step_func: Callable):
        super().__init__(dataset, canvas)

        self.update_step_func = update_step_func

        nsteps = self.dataset._widgets.nsteps

        self.label = Label(self.dataset._widgets.current_time_str)
        self.label.layout = Layout(width='150px')

        self.slider = IntSlider(value=0, min=0, max=nsteps - 1, readout=False)
        self.slider.layout = Layout(width='auto', flex='3 1 0%')
        self.slider.observe(self._update_time, names='value')

        self.play = Play(value=0, min=0, max=nsteps - 1, interval=100)

        self.play_speed = IntSlider(value=30, min=0, max=50, readout=False)
        self.play_speed.layout = Layout(width='auto', flex='1 1 0%')
        self.play_speed.observe(self._update_play_speed, names='value')

        jslink((self.play, 'value'), (self.slider, 'value'))

        self._widget = HBox(
            [
                self.play,
                Label('slow/fast: '),
                self.play_speed,
                Label('steps: '),
                self.slider,
                self.label,
            ],
            layout=Layout(width='100%'),
        )

    def _update_time(self, change):
        self.dataset._widgets.timestep = change['new']
        self.label.value = self.dataset._widgets.current_time_str

        with self.canvas.hold_sync():
            self.update_step_func()

    def _update_play_speed(self, change):
        speed_ms = int((520 + 500 * math.cos(change['new'] * math.pi / 50)) / 2)
        self.play.interval = speed_ms

    def go_to_step(self, step):
        self.slider.value = step

    def go_to_time(self, time):
        step = self.dataset._widgets.time_to_step(time)
        self.slider.value = step


class Coloring(IpyFastscapeWidget):
    def __init__(
        self,
        dataset: xr.Dataset,
        canvas: Any,
        update_var_func: Callable,
        update_range_func: Callable,
    ):
        super().__init__(dataset, canvas)

        self.update_var_func = update_var_func
        self.update_range_func = update_range_func

        self.var_dropdown = Dropdown(
            value=self.dataset._widgets.elevation_var,
            options=list(self.dataset._widgets.data_vars),
        )
        self.var_dropdown.observe(self._update_var, names='value')

        da = self.dataset._widgets.color
        self.min_input = FloatText(value=da.min(), layout=Layout(height='auto', width='auto'))
        self.max_input = FloatText(value=da.max(), layout=Layout(height='auto', width='auto'))

        self.rescale_button = Button(
            description='Rescale',
            tooltip='Rescale to actual data range',
            layout=Layout(height='auto', width='auto'),
        )
        self.rescale_button.on_click(lambda _: self._update_range())

        self.rescale_step_button = Button(
            description='Rescale Step',
            tooltip='Rescale to actual data range (current step)',
            layout=Layout(height='auto', width='auto'),
        )
        self.rescale_step_button.on_click(lambda _: self._update_range(step=True))

        range_grid = GridspecLayout(2, 2)
        range_grid[0, 0] = self.min_input
        range_grid[0, 1] = self.max_input
        range_grid[1, 0] = self.rescale_button
        if self.dataset._widgets.time_dim is not None:
            range_grid[1, 1] = self.rescale_step_button

        self._widget = VBox(
            [
                Label('Coloring:'),
                self.var_dropdown,
                Label('Color range:'),
                range_grid,
            ]
        )

    def _update_var(self, change):
        self.dataset._widgets.color_var = change['new']
        da = self.dataset._widgets.color

        with self.canvas.hold_sync():
            self.update_var_func()
            self.update_range_func(da)

    def _update_range(self, step=False):
        if step:
            da = self.dataset._widgets.current_color
        else:
            da = self.dataset._widgets.color

        with self.canvas.hold_sync():
            self.update_range_func(da)
