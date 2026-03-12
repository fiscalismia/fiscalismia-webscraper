"""Tests for scraping module and supermarket scraping routes."""

import re
import os
import json
import aiohttp
import pytest
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import patch
from dotenv import load_dotenv
from api.scraping import ScrapeResult, get_current_week_pattern

load_dotenv()
TOKEN = os.environ.get("TEST_BEARER_TOKEN", "")
BASE = "http://127.0.0.1:3003/fastapi/fiscalismia/rest"


# ── Unit tests ──────────────────────────────────────────────────────────────


class TestGetCurrentWeekPatternUnit:
    """Unit tests for get_current_week_pattern()."""

    def test_get_current_week_pattern_format(self):
        pattern = get_current_week_pattern()
        assert re.match(r"^kw\d{1,2}-\d{2}$", pattern), f"Unexpected format: {pattern}"

    def test_get_current_week_pattern_values(self):
        with patch("api.scraping.datetime") as mock_dt:
            # 2026-03-12 is ISO week 11
            fake_now = datetime(2026, 3, 12, 14, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))
            mock_dt.now.return_value = fake_now
            result = get_current_week_pattern()
            assert result == "kw11-26"

    def test_get_current_week_pattern_year_boundary(self):
        with patch("api.scraping.datetime") as mock_dt:
            # 2025-12-29 is ISO week 1 of 2026
            fake_now = datetime(2025, 12, 29, 14, 0, 0, tzinfo=ZoneInfo("Europe/Berlin"))
            mock_dt.now.return_value = fake_now
            result = get_current_week_pattern()
            assert result == "kw1-26"


class TestScrapeResultModelUnit:
    """Unit tests for ScrapeResult Pydantic model."""

    def test_scrape_result_model(self):
        result = ScrapeResult(
            status="success",
            session_id="test-123",
            target_url="https://example.com",
            prospekt_url="https://example.com/prospekt",
            timestamp="2026-03-12T14:00:00+01:00",
            data={"key": "value"},
        )
        assert result.status == "success"
        assert result.session_id == "test-123"
        assert result.prospekt_url == "https://example.com/prospekt"

    def test_scrape_result_json_serialization(self):
        result = ScrapeResult(
            status="error",
            session_id="test-456",
            target_url="https://example.com",
            timestamp="2026-03-12T14:00:00+01:00",
        )
        data = json.loads(result.model_dump_json())
        assert data["status"] == "error"
        assert data["prospekt_url"] is None
        assert data["data"] is None


# ── Integration tests (require running server + TEST_BEARER_TOKEN) ──────────


@pytest.mark.skipif(not TOKEN, reason="TEST_BEARER_TOKEN not set")
class TestAldiProspektEndpointIntegration:
    """Integration tests for the Aldi prospekt scraping endpoint."""

    @pytest.mark.asyncio
    async def test_aldi_prospekt_endpoint(self):
        headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{BASE}/cdp/scrape/supermarket/aldi_prospekt", headers=headers) as resp:
                assert resp.status == 200
                result = await resp.json()
                assert "session_id" in result
                assert "results_url" in result
                assert result["results_url"].startswith("/cdp/scrape/results/")

    @pytest.mark.asyncio
    async def test_scrape_results_not_found(self):
        headers = {"Authorization": f"Bearer {TOKEN}"}
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{BASE}/cdp/scrape/results/nonexistent-id", headers=headers) as resp:
                assert resp.status == 404
