"""Tests for _bioio_plugin_utils module."""


class TestSuggestPluginsForPath:
    """Test suggest_plugins_for_path function."""

    def test_czi_file(self):
        """Test that CZI file suggests bioio-czi."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path("test.czi")

        assert len(plugins) == 1
        assert plugins[0]["name"] == "bioio-czi"
        assert "Zeiss CZI" in plugins[0]["description"]

    def test_lif_file(self):
        """Test that LIF file suggests bioio-lif."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path("test.lif")

        assert len(plugins) == 1
        assert plugins[0]["name"] == "bioio-lif"

    def test_tiff_file_suggests_all(self):
        """Test that TIFF files suggest all TIFF-compatible plugins."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path("test.tiff")

        # Should get bioio-ome-tiff, bioio-tifffile, bioio-tiff-glob
        plugin_names = [p["name"] for p in plugins]
        assert "bioio-ome-tiff" in plugin_names
        assert "bioio-tifffile" in plugin_names
        assert "bioio-tiff-glob" in plugin_names

    def test_unsupported_extension(self):
        """Test that unsupported extensions return empty list."""
        from ndevio._bioio_plugin_utils import suggest_plugins_for_path

        plugins = suggest_plugins_for_path("test.xyz")

        assert len(plugins) == 0


class TestFilterInstalledPlugins:
    """Test filter_installed_plugins function."""

    def test_filters_out_installed_plugins(self):
        """Test that installed plugins are filtered from suggestions."""
        from ndevio._bioio_plugin_utils import filter_installed_plugins

        suggested = [
            {"name": "bioio-czi", "description": "Zeiss CZI files"},
            {"name": "bioio-lif", "description": "Leica LIF files"},
        ]

        # Mock feasibility report showing bioio-czi as installed
        # (presence in report means it's installed, regardless of 'supported')
        mock_report = {
            "bioio-czi": type("MockSupport", (), {"supported": False})(),
            "ArrayLike": type("MockSupport", (), {"supported": True})(),
        }

        filtered = filter_installed_plugins(suggested, mock_report)

        # bioio-czi should be filtered out, bioio-lif should remain
        assert len(filtered) == 1
        assert filtered[0]["name"] == "bioio-lif"

    def test_no_feasibility_report(self):
        """Test that None feasibility report returns all suggestions."""
        from ndevio._bioio_plugin_utils import filter_installed_plugins

        suggested = [
            {"name": "bioio-czi", "description": "Zeiss CZI files"},
            {"name": "bioio-lif", "description": "Leica LIF files"},
        ]

        # None report should return everything
        filtered = filter_installed_plugins(suggested, None)

        assert len(filtered) == 2

    def test_core_plugins_in_report(self):
        """Test that core plugins appearing in report are filtered correctly."""
        from ndevio._bioio_plugin_utils import filter_installed_plugins

        suggested = [
            {
                "name": "bioio-ome-tiff",
                "description": "OME-TIFF",
                "core": True,
            },
            {"name": "bioio-tifffile", "description": "TIFF files"},
        ]

        # bioio-ome-tiff is in the report (installed) even though it
        # couldn't read this particular file
        mock_report = {
            "bioio-ome-tiff": type("MockSupport", (), {"supported": False})(),
            "ArrayLike": type("MockSupport", (), {"supported": True})(),
        }

        filtered = filter_installed_plugins(suggested, mock_report)

        # bioio-ome-tiff should be filtered out (it's installed)
        # bioio-tifffile should remain
        assert len(filtered) == 1
        assert filtered[0]["name"] == "bioio-tifffile"


class TestGetMissingPluginsMessage:
    """Test get_missing_plugins_message function."""

    def test_czi_message_no_report(self):
        """Test message generation for CZI without feasibility report."""
        from ndevio._bioio_plugin_utils import get_missing_plugins_message

        message = get_missing_plugins_message("test.czi")

        assert "bioio-czi" in message
        assert "pip install" in message or "conda install" in message

    def test_unsupported_extension_message(self):
        """Test message for completely unsupported extension."""
        from ndevio._bioio_plugin_utils import get_missing_plugins_message

        message = get_missing_plugins_message("test.xyz")

        assert "No bioio plugins found" in message or ".xyz" in message
