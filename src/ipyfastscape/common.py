import math
from typing import Callable, Dict, Optional

import xarray as xr
from IPython.display import display
from ipywidgets import (
    Accordion,
    AppLayout,
    Button,
    DOMWidget,
    Dropdown,
    FloatText,
    GridspecLayout,
    HBox,
    IntSlider,
    Label,
    Layout,
    Output,
    Play,
    ToggleButton,
    VBox,
    jslink,
)

from .xr_accessor import WidgetsAccessor  # noqa: F401


class AppComponent:
    """Base class for ipyfastscape app components.

    Subclasses need to implement the `.setup()` method, which must return a
    widget (or container/layout widget).

    """

    def __init__(self, dataset: xr.Dataset, canvas: DOMWidget):
        self.dataset = dataset
        self.canvas = canvas
        self._widget = self.setup()

    def setup(self) -> DOMWidget:
        raise NotImplementedError()

    @property
    def widget(self) -> DOMWidget:
        return self._widget


class TimeStepper(AppComponent):
    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
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

        return HBox(
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

        if self.canvas_callback is not None:
            with self.canvas.hold_sync():
                self.canvas_callback()

    def _update_play_speed(self, change):
        speed_ms = int((520 + 500 * math.cos(change['new'] * math.pi / 50)) / 2)
        self.play.interval = speed_ms

    def go_to_step(self, step):
        self.slider.value = step

    def go_to_time(self, time):
        step = self.dataset._widgets.time_to_step(time)
        self.slider.value = step


class Coloring(AppComponent):
    def __init__(
        self, *args, canvas_callback_var: Callable = None, canvas_callback_range: Callable = None
    ):
        self.canvas_callback_var = canvas_callback_var
        self.canvas_callback_range = canvas_callback_range
        super().__init__(*args)

    def setup(self):
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

        return VBox(
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
            if self.canvas_callback_var is not None:
                self.canvas_callback_var()
            if self.canvas_callback_range is not None:
                self.canvas_callback_range(da)

    def _update_range(self, step=False):
        if step:
            da = self.dataset._widgets.current_color
        else:
            da = self.dataset._widgets.color

        if self.canvas_callback_range is not None:
            with self.canvas.hold_sync():
                self.canvas_callback_range(da)


class VizApp:
    """Base class for ipyfastscape's visualization apps."""

    dataset: Optional[xr.Dataset]
    canvas: Optional[DOMWidget]
    timestepper: Optional[TimeStepper]
    display_properties: Optional[Dict[str, AppComponent]]
    output: Output

    def __init__(self, dataset: xr.Dataset = None, canvas_height: int = 600, **kwargs):

        self._canvas_height = int(canvas_height)
        # add margin + header height
        self._output_height = self._canvas_height + 10 + 30

        self.canvas = None
        self.timestepper = None
        self.display_properties = None

        self.output = Output(layout=Layout(height=str(self._output_height) + 'px'))

        self.dataset = None

        if dataset is not None:
            self.load_dataset(dataset, **kwargs)

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

        # shallow copy of dataset to support multiple VizApp instances using the same dataset
        self.dataset = dataset.copy()
        self.dataset._widgets(x=x, y=y, elevation_var=elevation_var, time=time)

        self.reset_app()

    def _update_step(self):
        pass

    def _reset_canvas(self):
        pass

    def _reset_display_properties(self):
        pass

    def _resize_canvas(self):
        # TODO: proper canvas resizing
        # the workaround below is a hack (force change with before back to 100%)
        with self.canvas.hold_sync():
            self.canvas.layout.width = 'auto'
            self.canvas.layout.width = '100%'

    def reset_app(self):
        self.output.clear_output()

        self._reset_canvas()
        self.canvas.layout = Layout(
            width='100%',
            height=str(self._canvas_height) + 'px',
            overflow='hidden',
            border='solid 1px #bbb',
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
            self.timestepper = TimeStepper(
                self.dataset, self.canvas, canvas_callback=self._update_step
            )
            header_elements.append(self.timestepper.widget)

        # left pane
        self._reset_display_properties()
        display_properties_widgets = VBox([dp.widget for dp in self.display_properties.values()])

        left_pane = Accordion([display_properties_widgets])
        left_pane.set_title(0, 'Display properties')
        left_pane.layout = Layout(
            width='400px',
            height='95%',
            margin='0 10px 0 0',
            flex='0 0 auto',
        )

        def toggle_left_pane(change):
            if change['new']:
                left_pane.layout.display = 'block'
                self._resize_canvas()
            else:
                left_pane.layout.display = 'none'
                self._resize_canvas()

        menu_button.observe(toggle_left_pane, names='value')

        # app
        app = AppLayout(
            header=HBox(header_elements),
            left_sidebar=None,
            right_sidebar=None,
            center=HBox([left_pane, self.canvas]),
            footer=None,
            pane_heights=['30px', str(self._canvas_height) + 'px', 0],
            grid_gap='10px',
            width='100%',
            overflow='hidden',
        )

        with self.output:
            display(app)

    def show(self):
        display(self.output)
