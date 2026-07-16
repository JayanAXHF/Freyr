from shriteq.config import SiteConfig
from shriteq.forecast.load_forecaster import LoadForecaster
from shriteq.sim.load_profiles import generate_load_series


def test_load_forecaster_predicts_96_frames_without_nans():
    series = generate_load_series(SiteConfig(), "2026-01-05", days=28)
    frames = LoadForecaster().fit(series).predict(96)
    print(frames)
    assert len(frames) == 96
    assert all(frame.load_mean_kw == frame.load_mean_kw for frame in frames)
    assert all(
        frame.load_p10_kw <= frame.load_mean_kw <= frame.load_p90_kw for frame in frames
    )
    load_widths = [frame.load_p90_kw - frame.load_p10_kw for frame in frames]
    assert len({round(width, 8) for width in load_widths}) > 1
    solar_frames = [frame for frame in frames if frame.solar_mean_kw > 0]
    assert all(
        frame.solar_p10_kw < frame.solar_mean_kw < frame.solar_p90_kw
        for frame in solar_frames
    )
