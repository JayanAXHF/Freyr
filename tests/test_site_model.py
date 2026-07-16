from shriteq.config import SiteConfig
from shriteq.sim.site_model import SiteModel


def test_grid_import_hand_check():
    result = SiteModel(SiteConfig()).step(20, 5, 2, 3, 0, 0, 0)
    assert result["grid_import_kw"] == 14
