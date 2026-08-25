"""Geocoding helpers for human-readable weather place labels."""

from __future__ import annotations

from app.services.geocoding import _parse_lat_lon, format_place_label


def test_parse_lat_lon() -> None:
    assert _parse_lat_lon("30.27, -97.74") == (30.27, -97.74)
    assert _parse_lat_lon("Austin, TX") is None


def test_format_place_label_prefers_name() -> None:
    label = format_place_label(
        {"name": "Austin", "admin1": "Texas", "country": "United States"},
        "30.27,-97.74",
    )
    assert label.startswith("Austin")
    assert "Texas" in label


def test_format_place_label_does_not_keep_raw_coordinates() -> None:
    label = format_place_label({"name": "30.27,-97.74"}, "30.27,-97.74")
    assert _parse_lat_lon(label) is None
    assert label == "Unknown location"
