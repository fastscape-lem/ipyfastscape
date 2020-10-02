from typing import Callable

import numpy as np
import xarray as xr
from ipywidgets import HBox, IntSlider, Label, Layout, Play, jslink

from .xr_accessor import WidgetsAccessor  # noqa: F401


class IpyFastscapeWidget:
    def __init__(self, dataset: xr.Dataset):
        self.dataset = dataset
        self._widget = None

    def get_widget(self):
        return self._widget


class TimeStepper(IpyFastscapeWidget):
    def __init__(self, dataset: xr.Dataset, update_step_func: Callable):
        super().__init__(dataset)

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
        self.update_step_func(change)

    def _update_play_speed(self, change):
        speed_ms = int((520 + 500 * np.cos(change['new'] * np.pi / 50)) / 2)
        self.play.interval = speed_ms
