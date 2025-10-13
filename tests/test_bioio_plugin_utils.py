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


class TestReaderPluginManager:
    """Test ReaderPluginManager class."""

    def test_manager_filters_installed_plugins(self):
        """Test that manager correctly identifies installable plugins."""
        from unittest.mock import Mock, patch

        from ndevio import ReaderPluginManager

        # Mock feasibility report showing bioio-czi as installed
        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {
                "bioio-czi": Mock(supported=False),
                "ArrayLike": Mock(supported=False),
            }

            manager = ReaderPluginManager("test.czi")

            # bioio-czi should be in installed_plugins
            assert "bioio-czi" in manager.installed_plugins

            # bioio-czi should NOT be in installable_plugins (already installed)
            installable_names = [
                p["name"] for p in manager.installable_plugins
            ]
            assert "bioio-czi" not in installable_names

    def test_manager_suggests_uninstalled_plugins(self):
        """Test that manager suggests uninstalled plugins."""
        from unittest.mock import Mock, patch

        from ndevio import ReaderPluginManager

        # Mock feasibility report with no bioio-lif installed
        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {
                "bioio-ome-tiff": Mock(supported=False),
                "ArrayLike": Mock(supported=False),
            }

            manager = ReaderPluginManager("test.lif")

            # bioio-lif should be in suggested_plugins
            suggested_names = [p["name"] for p in manager.suggested_plugins]
            assert "bioio-lif" in suggested_names

            # bioio-lif should also be in installable_plugins
            installable_names = [
                p["name"] for p in manager.installable_plugins
            ]
            assert "bioio-lif" in installable_names

    def test_manager_excludes_core_plugins_from_installable(self):
        """Test that core plugins are excluded from installable list."""
        from unittest.mock import Mock, patch

        from ndevio import ReaderPluginManager

        # Mock report showing no plugins installed
        with patch("bioio.plugin_feasibility_report") as mock_report:
            mock_report.return_value = {
                "ArrayLike": Mock(supported=False),
            }

            manager = ReaderPluginManager("test.tiff")

            # Core plugins (like bioio-ome-tiff) should not be in installable
            installable_names = [
                p["name"] for p in manager.installable_plugins
            ]

            # bioio-ome-tiff is a core plugin, shouldn't need installation
            core_plugins = [
                "bioio-ome-tiff",
                "bioio-imageio",
                "bioio-ome-zarr",
            ]
            for core in core_plugins:
                assert core not in installable_names

            # bioio-tifffile is not core, should be installable
            assert "bioio-tifffile" in installable_names


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
