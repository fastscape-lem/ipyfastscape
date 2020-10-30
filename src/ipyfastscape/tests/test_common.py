import pytest
import xarray as xr

from ipyfastscape.common import AppComponent


def test_app_component(dataset_init):

    with pytest.raises(NotImplementedError):
        AppComponent(dataset_init)

    class DummyAppComponent(AppComponent):
        def setup(self):
            return 'widget'

    component = DummyAppComponent(dataset_init)

    xr.testing.assert_identical(component.dataset, dataset_init)
    assert component.widget == 'widget'
    assert component.linkable_traits == []
