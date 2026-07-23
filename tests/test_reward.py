from shriteq.env.reward import compute_reward
from shriteq.config import SiteConfig


def test_new_peak_is_penalized():
    no_peak = compute_reward(SiteConfig(), 1, 8, 0, 250, 0, 0)
    new_peak = compute_reward(SiteConfig(), 1, 8, 1, 250, 0, 0)
    assert new_peak < no_peak
