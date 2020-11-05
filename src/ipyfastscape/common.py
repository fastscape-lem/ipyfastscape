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
    def widget(self) -> widgets.Widget:
        return self._widget

    @property
    def linkable_traits(self) -> List[Tuple[widgets.Widget, str]]:
        return []


class DimensionExplorer(AppComponent):
    """Provides controls for exploring extra-dimensions of a Dataset (i.e.,
    non-space, non-time).

    """

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
    """Provides animation controls for temporal or other iterative data."""

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
        """Select a given (time) step."""
        self.slider.value = step

    def go_to_time(self, time):
        """Select a given time (or step label).

        Select the step that is the closest to the given time/label.

        """
        step = self.dataset._widgets.time_to_step(time)
        self.slider.value = step


class Coloring(AppComponent):
    """Provides controls for colored data (e.g., heatmap, isocolor)."""

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
            options=list(self.color_vars),
        )
        self.var_dropdown.observe(lambda change: self._set_color_var(change['new']), names='value')

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
        self.rescale_button.on_click(lambda _: self.reset_color_limits())

        self.rescale_step_button = widgets.Button(
            description='Rescale Step',
            tooltip='Rescale to actual data range (current step)',
            layout=widgets.Layout(height='auto', width='auto'),
        )
        self.rescale_step_button.on_click(lambda _: self.reset_color_limits(step=True))

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

    @property
    def color_vars(self) -> Tuple[str]:
        """Returns all possible color variables."""
        return tuple(self.dataset._widgets.data_vars)

    def _set_color_var(self, var_name):
        self.dataset._widgets.color_var = var_name

        if self.canvas_callback_var is not None:
            self.canvas_callback_var()
        if self.canvas_callback_range is not None:
            self.canvas_callback_range()

    def set_color_var(self, var_name):
        """Map the coloring to a data variable.

        Parameters
        ----------
        var_name : str
            Name of the data variable (must be one of the names
            returned by the ``color_vars`` property).

        """
        if var_name not in self.color_vars:
            raise ValueError(f'Invalid variable name {var_name}, must be one of {self.color_vars}')

        self.var_dropdown.value = var_name

    def set_color_limits(self, vmin: Union[int, float], vmax: Union[int, float]):
        """Set the colormap limits to the given min/max values."""
        self.min_input.value = vmin
        self.max_input.value = vmax

    def reset_color_limits(self, step=False):
        """Reset color limits to data range.

        Parameters
        ----------
        step : bool
            If true, resets the color range to the range of the data that is shown
            in the current scene. Otherwise (default), resets the color range to the
            whole data range.

        """
        if self.canvas_callback_range is not None:
            self.canvas_callback_range(step=step)


class VizApp:
    """Base class for ipyfastscape's visualization apps."""

    dataset: Optional[xr.Dataset]
    components: Dict[str, AppComponent]

    def __init__(self, dataset: xr.Dataset = None, canvas_height: int = 600, **kwargs):
        """

        Parameters
        ----------
        dataset : xr.Dataset
            Visualization data.
        canvas_height : int
            Height of figure or scene canvas, in pixels.
        **kwargs
            Keyword arguments passed to ``.load_dataset()``.

        """
        self._canvas_height = int(canvas_height)
        self._canvas = widgets.DOMWidget()
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
        """Load a new dataset and reset the application.

        Parameters
        ----------
        dataset : xr.Dataset
            Visualization data.
        x_dim : str, optional
            Name of the dimension in the dataset corresponding to the 'x' axis.
        y_dim : str, optional
            Name of the dimension in the dataset corresponding to the 'y' axis.
        elevation_var : str, optional
            Name of the data variable that contains elevation values. This data
            variable must contain the dimensions labels given here as arguments.
        time_dim : str, optional
            Name of the time or step dimension in the dataset. If no dimension
            is given (default), any dimension other than ``x_dim`` and ``y_dim``
            will be considered as an extra dimension.

        Notes
        -----
        The application will retain in the dataset all data variables that have
        the same dimension labels than ``elevation_var``.

        """
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
        """Returns the figure or scene canvas."""
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
        """Clear output and reset the whole application."""
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
    def widget(self) -> widgets.Output:
        """Returns the application's output widget."""
        return self._output

    def show(self):
        """Display the application."""
        display(self._output)


class AppLinker:
    """Provides some UI controls to easily link controls from two
    or more applications.

    This is useful for, e.g., comparing different models or datasets
    side-by-side.

    """

    def __init__(self, apps: List[VizApp], link_client=True, link_server=False):
        """

        Parameters
        ----------
        apps : list of :class:`ipyfastscape.VizApp` objects
            Application objects to link. The list must at least contain
            two different application instances.
        link_client : bool
            If True (default), link application components on the client side.
        link_server : bool
            If True, link application components on the server side (default, False).

        """
        if not all([isinstance(app, VizApp) for app in apps]):
            raise TypeError('`app` argument only accepts VizApp objects')

        if len(apps) < 2:
            raise ValueError('AppLinker works with at least two VizApp objects')

        if len(set(apps)) < len(apps):
            raise ValueError('AppLinker works with distinct VizApp objects')

        self._apps = apps
        self._link_client = link_client
        self._link_server = link_server
        self._widget = self.setup()

    def _linker_button_observe_factory(self, comp_objs: List[AppComponent]) -> Callable:
        c0 = comp_objs[0]
        comps = comp_objs[1:]

        link_objs = []

        def on_click(change):
            if change['new']:
                for c in comps:
                    for source, target in zip(c0.linkable_traits, c.linkable_traits):
                        if self._link_client:
                            link_objs.append(widgets.jslink(source, target))
                        if self._link_server:
                            link_objs.append(widgets.link(source, target))
            else:
                for link in link_objs:
                    link.unlink()
                link_objs.clear()

        return on_click

    def _create_linker_button(self, comp_name: str) -> Union[widgets.ToggleButton, None]:
        comp_objs = [app.components[comp_name] for app in self._apps]

        comp_cls = type(comp_objs[0])
        allow_link = getattr(comp_cls, 'allow_link', False)
        same_type = all([isinstance(obj, comp_cls) for obj in comp_objs])

        if not allow_link or not same_type:
            return None

        layout = widgets.Layout(width='200px')
        button = widgets.ToggleButton(
            value=False, description=f'Link {comp_cls.name}', layout=layout
        )
        button.observe(self._linker_button_observe_factory(comp_objs), names='value')

        return button

    def setup(self):
        app_components = set().union(*[app.components for app in self._apps])

        buttons = [self._create_linker_button(comp_name) for comp_name in app_components]
        self.buttons = [b for b in buttons if b is not None]

        return widgets.HBox(self.buttons)

    @property
    def widget(self) -> widgets.Widget:
        """Return the application linker as a widget."""
        return self._widget

    def show(self):
        """Display the application linker."""
        display(self.widget)
