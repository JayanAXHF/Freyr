from shriteq.env.reward import compute_reward
from shriteq.config import SiteConfig
import pytest


def test_new_peak_is_penalized():
    no_peak = compute_reward(SiteConfig(), 1, 8, 0, 250, 0, 0)
    new_peak = compute_reward(SiteConfig(), 1, 8, 1, 250, 0, 0)
    assert new_peak < no_peak


@pytest.mark.parametrize("unmet_penalty", [100.0, 1000.0])
def test_reward_uses_caller_config(unmet_penalty):
    config = SiteConfig(unmet_penalty=unmet_penalty)
    reward = compute_reward(config, 0, 0, 0, 0, 1, 0)
    assert reward == -unmet_penalty


def test_deferred_penalty_is_nonnegative_and_monotonic():
    from shriteq.env.reward import deferred_penalty

    config = SiteConfig()
    assert deferred_penalty(config, 0.0) == 0.0
    assert deferred_penalty(config, 20.0) > deferred_penalty(config, 1.25)
