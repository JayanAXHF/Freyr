"""Time-of-use tariff and demand-charge tracking."""

from datetime import datetime, timedelta

from shriteq.config import SiteConfig


class TariffModel:
    def __init__(self, config: SiteConfig):
        self.config = config
        self.current_billing_peak_kva = 0.0
        self._cycle_start: datetime | None = None

    def _reset_cycle_if_needed(self, timestamp: datetime) -> None:
        if self._cycle_start is None:
            self._cycle_start = timestamp
            return
        if timestamp >= self._cycle_start + timedelta(days=30):
            cycles = (timestamp - self._cycle_start).days // 30
            self._cycle_start += timedelta(days=30 * cycles)
            self.current_billing_peak_kva = 0.0

    def tariff_block(self, timestamp: datetime) -> tuple[int, float, int]:
        hour = timestamp.hour + timestamp.minute / 60
        blocks = self.config.tariff_blocks
        for index, block in enumerate(blocks):
            start = block["start_hour"]
            end = block["end_hour"]
            if start <= hour < end:
                minutes = int((end - hour) * 60)
                return index, block["price_inr_per_kwh"], minutes

        # Permit a tariff schedule whose final block wraps through midnight.
        for index, block in enumerate(blocks):
            if block["start_hour"] > block["end_hour"] and (
                hour >= block["start_hour"] or hour < block["end_hour"]
            ):
                if hour >= block["start_hour"]:
                    minutes = int(((24 - hour) + block["end_hour"]) * 60)
                else:
                    minutes = int((block["end_hour"] - hour) * 60)
                return index, block["price_inr_per_kwh"], minutes
        raise ValueError(f"timestamp {timestamp!r} is outside the tariff blocks")

    # Backwards-compatible private alias for callers that used the original
    # helper name.
    _tariff_block = tariff_block

    def peek(self, timestamp: datetime) -> tuple[int, float, int]:
        """Return tariff information without changing billing state."""
        return self.tariff_block(timestamp)

    def step(self, timestamp: datetime, grid_import_kva: float) -> dict:
        self._reset_cycle_if_needed(timestamp)
        tariff_block_id, price, minutes = self.tariff_block(timestamp)
        peak_bump = max(0.0, grid_import_kva - self.current_billing_peak_kva)
        if grid_import_kva > self.current_billing_peak_kva:
            self.current_billing_peak_kva = grid_import_kva
        return {
            "tod_price_inr_per_kwh": price,
            "tariff_block_id": tariff_block_id,
            "minutes_to_tariff_change": minutes,
            "current_billing_peak_kva": self.current_billing_peak_kva,
            "peak_bump_kva": peak_bump,
        }
