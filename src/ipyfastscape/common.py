import math
from collections import defaultdict
from typing import Callable, Dict, List, Optional, Tuple, Union

import ipywidgets as widgets
import xarray as xr
from IPython.display import display

from .xr_accessor import WidgetsAccessor  # noqa: F401


class AppComponent:
    """Base class for ipyfastscape app components.

    Subclasses need to implement the `.setup()` method, which must return a
    widget (or container/layout widget).

    """

    allow_link: bool = True
    name: Optional[str] = None

    def __init__(self, dataset: xr.Dataset):
        self.dataset = dataset
        self._widget = self.setup()

    def setup(self) -> widgets.Widget:
        raise NotImplementedError()

    @property
    def widget(self) -> widgets.DOMWidget:
        return self._widget

    @property
    def linkable_traits(self) -> List[Tuple[widgets.Widget, str]]:
        return []


class DimensionExplorer(AppComponent):
    name = 'Dimensions'

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

    @property
    def linkable_traits(self):
        return [(sl, 'value') for sl in self.sliders.values()]

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
            self.canvas_callback()


class TimeStepper(AppComponent):
    name = 'Steps'

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

    @property
    def linkable_traits(self):
        return [(self.slider, 'value'), (self.play, 'value'), (self.play_speed, 'value')]

    def _update_step(self, change):
        self.dataset._widgets.timestep = change['new']
        self.label.value = self.dataset._widgets.current_time_fmt

        if self.canvas_callback is not None:
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
    allow_link = False
    name = 'Coloring'

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

        if self.canvas_callback_var is not None:
            self.canvas_callback_var()
        if self.canvas_callback_range is not None:
            self.canvas_callback_range()

    def _update_range(self, step=False):
        if self.canvas_callback_range is not None:
            self.canvas_callback_range(step=step)


class VizApp:
    """Base class for ipyfastscape's visualization apps."""

    dataset: Optional[xr.Dataset]
    components: Dict[str, AppComponent]

    def __init__(self, dataset: xr.Dataset = None, canvas_height: int = 600, **kwargs):

        self._canvas_height = int(canvas_height)
        self._canvas = None
        self._output = widgets.Output()
        self.components = {}

        if dataset is not None:
            self.load_dataset(dataset, **kwargs)
        else:
            self.dataset = None

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

    @property
    def canvas(self) -> widgets.DOMWidget:
        return self._canvas

    def _reset_canvas(self):
        pass

    def _redraw_canvas(self):
        pass

    def _resize_canvas(self):
        # TODO: proper canvas resizing
        # the workaround below is a hack (force change with before back to 100%)
        with self.canvas.hold_sync():
            self.canvas.layout.width = 'auto'
            self.canvas.layout.width = '100%'

    def _get_display_properties(self) -> Dict[str, AppComponent]:
        return {}

    def reset_app(self):
        self._output.clear_output()

        output_height = self._canvas_height

        if self.dataset._widgets.time_dim is not None:
            # add margin + header
            output_height += 10 + 30

        self._output.layout = widgets.Layout(height=str(output_height) + 'px')

        self.components['canvas'] = self._reset_canvas()
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
            timestepper = TimeStepper(self.dataset, canvas_callback=self._redraw_canvas)
            self.components['timestepper'] = timestepper
            header_elements.append(timestepper.widget)

        # left pane
        accordion_elements = []
        accordion_titles = []

        if len(self.dataset._widgets.extra_dims):
            dim_explorer = DimensionExplorer(self.dataset, canvas_callback=self._redraw_canvas)
            self.components['dimensions'] = dim_explorer
            accordion_elements.append(dim_explorer.widget)
            accordion_titles.append('Dimensions')

        display_properties = self._get_display_properties()
        self.components.update(display_properties)
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

        with self._output:
            display(app)

    @property
    def widget(self) -> widgets.Widget:
        return self._output

    def show(self):
        display(self._output)


def _linker_button_observe_factory(comp_objs: List[AppComponent]) -> Callable:
    c0 = comp_objs[0]
    comps = comp_objs[1:]

    link_objs = []

    def on_click(change):
        if change['new']:
            for c in comps:
                for source, target in zip(c0.linkable_traits, c.linkable_traits):
                    link = widgets.jslink(source, target)
                    link_objs.append(link)
        else:
            for link in link_objs:
                link.unlink()
            link_objs.clear()

    return on_click


def _create_linker_button(apps: List[VizApp], comp_name: str) -> Union[widgets.ToggleButton, None]:
    comp_objs = [app.components[comp_name] for app in apps]

    comp_cls = type(comp_objs[0])
    same_type = all([isinstance(obj, comp_cls) for obj in comp_objs])

    if not comp_cls.allow_link or not same_type:
        return None

    layout = widgets.Layout(width='200px')
    button = widgets.ToggleButton(value=False, description=f'Link {comp_cls.name}', layout=layout)
    button.observe(_linker_button_observe_factory(comp_objs), names='value')

    return button


class AppLinker:
    def __init__(self, apps: List[VizApp]):

        if not all([isinstance(app, VizApp) for app in apps]):
            raise TypeError('`app` argument only accepts VizApp objects')

        if len(apps) < 2:
            raise ValueError('AppLinker works with at least two VizApp objects')

        if len(set(apps)) < len(apps):
            raise ValueError('AppLinker works with distinct VizApp objects')

        self._apps = apps
        self._widget = self.setup()

    def setup(self):

        app_components = set().union(*[app.components for app in self._apps])

        buttons = [_create_linker_button(self._apps, comp_name) for comp_name in app_components]
        self.buttons = [b for b in buttons if b is not None]

        return widgets.HBox(self.buttons)

    @property
    def widget(self) -> widgets.Widget:
        return self._widget

    def show(self):
        display(self.widget)
