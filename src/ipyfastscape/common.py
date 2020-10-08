import math
from collections import defaultdict
from typing import Callable, Dict, Optional

import ipywidgets as widgets
import xarray as xr
from IPython.display import display

from .xr_accessor import WidgetsAccessor  # noqa: F401


class AppComponent:
    """Base class for ipyfastscape app components.

    Subclasses need to implement the `.setup()` method, which must return a
    widget (or container/layout widget).

    """

    def __init__(self, dataset: xr.Dataset, canvas: widgets.DOMWidget):
        self.dataset = dataset
        self.canvas = canvas
        self._widget = self.setup()

    def setup(self) -> widgets.DOMWidget:
        raise NotImplementedError()

    @property
    def widget(self) -> widgets.DOMWidget:
        return self._widget


class DimensionExplorer(AppComponent):
    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
        self.sliders = {}
        self.value_labels = defaultdict(list)
        vbox_elements = []

        extra_dims_names = self.dataset._widgets.extra_dims_names
        extra_dims_sizes = self.dataset._widgets.extra_dims_sizes

        for dim in self.dataset._widgets.extra_dims:

            for n in extra_dims_names[dim]:
                name_label = widgets.Label(f'{n}: ')
                value_label = widgets.Label('')

                self.value_labels[dim].append(value_label)
                vbox_elements.append(widgets.HBox([name_label, value_label]))

            slider = widgets.IntSlider(
                value=0,
                min=0,
                max=extra_dims_sizes[dim] - 1,
                readout=False,
                continuous_update=False,
            )
            slider.layout = widgets.Layout(width='95%')
            slider.observe(self._update_explorer)
            self.sliders[dim] = slider
            vbox_elements.append(slider)

        self._update_value_labels()

        return widgets.VBox(vbox_elements, layout=widgets.Layout(width='100%'))

    def _update_value_labels(self):
        extra_dims_fmt = self.dataset._widgets.extra_dims_fmt

        for dim, labels in self.value_labels.items():
            for lb, val in zip(labels, extra_dims_fmt[dim]):
                lb.value = val

    def _update_explorer(self, _):
        new_positions = {dim: s.value for dim, s in self.sliders.items()}
        self.dataset._widgets.update_extra_dims(new_positions)

        self._update_value_labels()

        if self.canvas_callback is not None:
            with self.canvas.hold_sync():
                self.canvas_callback()


class TimeStepper(AppComponent):
    def __init__(self, *args, canvas_callback: Callable = None):
        self.canvas_callback = canvas_callback
        super().__init__(*args)

    def setup(self):
        nsteps = self.dataset._widgets.nsteps

        self.label = widgets.Label(self.dataset._widgets.current_time_fmt)
        self.label.layout = widgets.Layout(width='150px')

        self.slider = widgets.IntSlider(value=0, min=0, max=nsteps - 1, readout=False)
        self.slider.layout = widgets.Layout(width='auto', flex='3 1 0%')
        self.slider.observe(self._update_step, names='value')

        self.play = widgets.Play(value=0, min=0, max=nsteps - 1, interval=100)

        self.play_speed = widgets.IntSlider(value=30, min=0, max=50, readout=False)
        self.play_speed.layout = widgets.Layout(width='auto', flex='1 1 0%')
        self.play_speed.observe(self._update_play_speed, names='value')

        widgets.jslink((self.play, 'value'), (self.slider, 'value'))

        return widgets.HBox(
            [
                self.play,
                widgets.Label('slow/fast: '),
                self.play_speed,
                widgets.Label('steps: '),
                self.slider,
                self.label,
            ],
            layout=widgets.Layout(width='100%'),
        )

    def _update_step(self, change):
        self.dataset._widgets.timestep = change['new']
        self.label.value = self.dataset._widgets.current_time_fmt

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
        self.var_dropdown = widgets.Dropdown(
            value=self.dataset._widgets.elevation_var,
            options=list(self.dataset._widgets.data_vars),
        )
        self.var_dropdown.observe(self._update_var, names='value')

        da = self.dataset._widgets.color
        self.min_input = widgets.FloatText(
            value=da.min(), layout=widgets.Layout(height='auto', width='auto')
        )
        self.max_input = widgets.FloatText(
            value=da.max(), layout=widgets.Layout(height='auto', width='auto')
        )

        self.rescale_button = widgets.Button(
            description='Rescale',
            tooltip='Rescale to actual data range',
            layout=widgets.Layout(height='auto', width='auto'),
        )
        self.rescale_button.on_click(lambda _: self._update_range())

        self.rescale_step_button = widgets.Button(
            description='Rescale Step',
            tooltip='Rescale to actual data range (current step)',
            layout=widgets.Layout(height='auto', width='auto'),
        )
        self.rescale_step_button.on_click(lambda _: self._update_range(step=True))

        range_grid = widgets.GridspecLayout(2, 2)
        range_grid[0, 0] = self.min_input
        range_grid[0, 1] = self.max_input
        range_grid[1, 0] = self.rescale_button
        if self.dataset._widgets.time_dim is not None:
            range_grid[1, 1] = self.rescale_step_button

        return widgets.VBox(
            [
                widgets.Label('Coloring:'),
                self.var_dropdown,
                widgets.Label('Color range:'),
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
    canvas: Optional[widgets.DOMWidget]
    app_components: Dict[str, AppComponent]
    output: widgets.Output

    def __init__(self, dataset: xr.Dataset = None, canvas_height: int = 600, **kwargs):

        self._canvas_height = int(canvas_height)
        # add margin + header height
        self._output_height = self._canvas_height + 10 + 30

        self.canvas = None
        self.app_components = {}

        self.output = widgets.Output(layout=widgets.Layout(height=str(self._output_height) + 'px'))

        self.dataset = None

        if dataset is not None:
            self.load_dataset(dataset, **kwargs)

    def load_dataset(
        self,
        dataset: xr.Dataset,
        x_dim: str = 'x',
        y_dim: str = 'y',
        elevation_var: str = 'topography__elevation',
        time_dim: Optional[str] = None,
    ):
        if not isinstance(dataset, xr.Dataset):
            raise TypeError(f'{dataset} is not a xarray.Dataset object')

        # shallow copy of dataset to support multiple VizApp instances using the same dataset
        self.dataset = dataset.copy()
        self.dataset._widgets(
            x_dim=x_dim, y_dim=y_dim, elevation_var=elevation_var, time_dim=time_dim
        )

        self.reset_app()

    def _update_step(self):
        pass

    def _reset_canvas(self):
        pass

    def _get_display_properties(self) -> Dict[str, AppComponent]:
        return {}

    def _resize_canvas(self):
        # TODO: proper canvas resizing
        # the workaround below is a hack (force change with before back to 100%)
        with self.canvas.hold_sync():
            self.canvas.layout.width = 'auto'
            self.canvas.layout.width = '100%'

    def reset_app(self):
        self.output.clear_output()

        self._reset_canvas()
        self.canvas.layout = widgets.Layout(
            width='100%',
            height=str(self._canvas_height) + 'px',
            overflow='hidden',
            border='solid 1px #bbb',
        )

        # header
        header_elements = []

        menu_button = widgets.ToggleButton(
            value=True,
            tooltip='Show/Hide sidebar',
            icon='bars',
            layout=widgets.Layout(width='50px', height='auto', margin='0 10px 0 0'),
        )

        header_elements.append(menu_button)

        if self.dataset._widgets.time_dim is not None:
            timestepper = TimeStepper(self.dataset, self.canvas, canvas_callback=self._update_step)
            self.app_components['timestepper'] = timestepper
            header_elements.append(timestepper.widget)

        # left pane
        accordion_elements = []
        accordion_titles = []

        if len(self.dataset._widgets.extra_dims):
            dim_explorer = DimensionExplorer(
                self.dataset, self.canvas, canvas_callback=self._update_step
            )
            self.app_components['dimensions'] = dim_explorer
            accordion_elements.append(dim_explorer.widget)
            accordion_titles.append('Dimensions')

        display_properties = self._get_display_properties()
        self.app_components.update(display_properties)
        display_properties_box = widgets.VBox([dp.widget for dp in display_properties.values()])
        accordion_elements.append(display_properties_box)
        accordion_titles.append('Display properties')

        left_pane = widgets.Accordion(accordion_elements)

        for pos, title in enumerate(accordion_titles):
            left_pane.set_title(pos, title)

        left_pane.layout = widgets.Layout(
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
        app = widgets.AppLayout(
            header=widgets.HBox(header_elements),
            left_sidebar=None,
            right_sidebar=None,
            center=widgets.HBox([left_pane, self.canvas]),
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
