from __future__ import annotations

import ast
import logging
import re
import time
from collections.abc import Generator
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from magicclass.widgets import (
    GroupBoxContainer,
    ScrollableContainer,
)
from magicgui.widgets import (
    CheckBox,
    Container,
    FileEdit,
    Label,
    LineEdit,
    ProgressBar,
    PushButton,
    TextEdit,
    TupleEdit,
)
from ndev_settings import get_settings

from ndevio import helpers

if TYPE_CHECKING:
    import napari
    from bioio import BioImage
    from bioio_base.types import PhysicalPixelSizes
    from napari.layers import Layer


def save_ome_tiff(
    data: np.ndarray,
    uri: Path,
    dim_order: str = "TCZYX",
    channel_names: list[str] | None = None,
    image_name: str | None = None,
    physical_pixel_sizes: PhysicalPixelSizes | None = None,
) -> None:
    """Save data as OME-TIFF with automatic dtype and channel name handling.

    Converts int64 to int32 for bioio compatibility. Validates channel_names
    count matches the data's channel dimension; if mismatched, channel_names
    are ignored.

    Parameters
    ----------
    data : np.ndarray
        The image data to save.
    uri : Path
        Path to save the file.
    dim_order : str, optional
        Dimension order string, by default 'TCZYX'.
    channel_names : list[str] | None, optional
        Channel names for OME metadata. Ignored if count doesn't match
        the channel dimension of data.
    image_name : str | None, optional
        Image name for OME metadata.
    physical_pixel_sizes : PhysicalPixelSizes | None, optional
        Physical pixel sizes for OME metadata.

    """
    from bioio.writers import OmeTiffWriter

    # Convert int64 to int32 for bioio compatibility
    # See: https://github.com/napari/napari/issues/5545
    if data.dtype == np.int64:
        data = data.astype(np.int32)

    # Validate channel_names count matches data
    if channel_names is not None and dim_order:
        channel_idx = dim_order.upper().find("C")
        if channel_idx != -1:
            if channel_idx >= len(data.shape):
                logging.warning(
                    "dim_order %r has C at index %d, but data has only %d "
                    "dimensions. Ignoring channel_names.",
                    dim_order,
                    channel_idx,
                    len(data.shape),
                )
                channel_names = None
            else:
                num_channels = data.shape[channel_idx]
                if len(channel_names) != num_channels:
                    channel_names = None  # Ignore mismatched channel names

    OmeTiffWriter.save(
        data=data,
        uri=uri,
        dim_order=dim_order or None,
        channel_names=channel_names,
        image_name=image_name or None,
        physical_pixel_sizes=physical_pixel_sizes,
    )


def concatenate_and_save_files(
    file_set: tuple[list[Path], str],
    save_directory: Path,
    channel_names: list[str] | None,
    p_sizes: PhysicalPixelSizes,
) -> Path:
    """Concatenate image files and save as OME-TIFF.

    This function concatenates multiple image files along the channel axis
    and saves the result as an OME-TIFF file.

    Parameters
    ----------
    file_set : tuple[list[Path], str]
        Tuple of (files, save_name) where files is a list of image files
        to concatenate and save_name is the base name for the output file.
    save_directory : Path
        Directory to save the output file.
    channel_names : list[str] | None
        Channel names for OME metadata. If None, defaults are used.
    p_sizes : PhysicalPixelSizes
        Physical pixel sizes for OME metadata.

    Returns
    -------
    Path
        Path to the saved output file.

    """
    files, save_name = file_set

    # Concatenate files
    from ndevio import nImage

    array_list = []
    for file in files:
        img = nImage(file)
        if "S" in img.dims.order:
            img_data = img.get_image_data("TSZYX")
        else:
            img_data = img.data

        # Iterate over the channel dimension (index 1) and only keep non-blank
        for idx in range(img_data.shape[1]):
            array = img_data[:, [idx], :, :, :]
            if array.max() > 0:
                array_list.append(array)

    if not array_list:
        raise ValueError(
            f"No valid channels found in files: {[str(f) for f in files]}"
        )

    img_data = np.concatenate(array_list, axis=1)

    # Save as OME-TIFF
    save_directory.mkdir(parents=True, exist_ok=True)
    save_path = save_directory / f"{save_name}.tiff"

    save_ome_tiff(
        data=img_data,
        uri=save_path,
        dim_order="TCZYX",
        channel_names=channel_names,
        image_name=save_name,
        physical_pixel_sizes=p_sizes,
    )

    return save_path


def extract_and_save_scenes_ome_tiff(
    file_path: Path,
    save_directory: Path,
    scenes: list[int | str] | None = None,
    channel_names: list[str] | None = None,
    p_sizes: PhysicalPixelSizes | None = None,
    base_save_name: str | None = None,
) -> Generator[tuple[int, str], None, None]:
    """Extract and save scenes from an image file as OME-TIFF.

    This function extracts specified scenes from a multi-scene image file
    and saves each as a separate OME-TIFF file. It yields progress updates
    for each scene processed.

    Parameters
    ----------
    file_path : Path
        Path to the source image file.
    save_directory : Path
        Directory to save the extracted scenes.
    scenes : list[int | str] | None, optional
        List of scene indices or names to extract. If None or empty,
        extracts all scenes. Empty list is treated as "process all".
    channel_names : list[str] | None, optional
        Channel names for OME metadata. If None, defaults are used.
    p_sizes : PhysicalPixelSizes, optional
        Physical pixel sizes for OME metadata.
    base_save_name : str | None, optional
        Base name for saved files. If None, uses the source filename stem.

    Yields
    ------
    tuple[int, str]
        Tuple of (scene_index, scene_name) for each processed scene.

    """
    from ndevio import nImage

    img = nImage(file_path)

    # Use all scenes if none specified or empty list provided
    # (empty list intentionally means "process all scenes")
    scenes_to_process = scenes if scenes else list(img.scenes)

    # Create save directory
    save_directory.mkdir(parents=True, exist_ok=True)

    # Use filename stem as base name if not provided
    if base_save_name is None:
        base_save_name = file_path.stem

    for scene in scenes_to_process:
        img.set_scene(scene)

        # Create ID string for this scene
        image_id = helpers.create_id_string(img, base_save_name)
        save_path = save_directory / f"{image_id}.tiff"

        save_ome_tiff(
            data=img.data,
            uri=save_path,
            dim_order="TCZYX",
            channel_names=channel_names,
            image_name=image_id,
            physical_pixel_sizes=p_sizes,
        )

        yield (img.current_scene_index, img.current_scene)


class UtilitiesContainer(ScrollableContainer):
    """
    A widget to work with images and labels in the napari viewer.

    Parameters
    ----------
    viewer: napari.viewer.Viewer, optional
        The napari viewer instance.

    """

    def __init__(self, viewer: napari.viewer.Viewer = None):
        """
        Initialize the UtilitiesContainer widget.

        Parameters
        ----------
        viewer : napari.viewer.Viewer, optional
            The napari viewer instance.

        """
        super().__init__(labels=False)

        self.min_width = 500  # TODO: remove this hardcoded value
        self._viewer = viewer if viewer is not None else None
        self._squeezed_dims_order: str | None = None
        self._squeezed_dims: tuple[int, ...] | None = None
        self._settings = get_settings()

        self._init_widgets()
        self._init_save_name_container()
        self._init_open_image_container()
        self._init_metadata_container()
        self._init_concatenate_files_container()
        self._init_save_layers_container()
        self._init_scene_container()
        self._init_layout()
        self._connect_events()
        self._init_batch_runner()

    def _init_batch_runner(self):
        """Initialize the BatchRunner for batch operations."""
        from nbatch import BatchRunner

        self._batch_runner = BatchRunner(
            on_start=self._on_batch_start,
            on_item_complete=self._on_batch_item_complete,
            on_complete=self._on_batch_complete,
            on_error=self._on_batch_error,
        )

    def _on_batch_start(self, total: int):
        """Callback when batch starts - initialize progress bar."""
        self._progress_bar.label = f"Processing {total} file sets"
        self._progress_bar.value = 0
        self._progress_bar.max = total
        self._set_batch_button_state(running=True)

    def _on_batch_item_complete(self, result, ctx):
        """Callback when a batch item completes."""
        self._progress_bar.value = ctx.index + 1
        # ctx.item is (files, save_name) tuple
        _, save_name = ctx.item
        self._progress_bar.label = f"Processed {save_name}"

    def _on_batch_complete(self):
        """Callback when the entire batch completes."""
        total = self._progress_bar.max
        errors = self._batch_runner.error_count
        if errors > 0:
            self._progress_bar.label = (
                f"Completed {total - errors} file sets ({errors} Errors)"
            )
        else:
            self._progress_bar.label = f"Completed {total} file sets"
        self._set_batch_button_state(running=False)
        self._results.value = (
            "Batch concatenated files in directory."
            f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _on_batch_error(self, ctx, exception):
        """Callback when a batch item fails."""
        _, save_name = ctx.item
        error_msg = str(exception)
        if len(error_msg) > 100:
            error_msg = error_msg[:100] + "..."
        self._progress_bar.label = f"Error on {save_name}: {error_msg}"

    def _set_batch_button_state(self, running: bool):
        """Update batch button appearance based on running state."""
        if running:
            self._concatenate_batch_button.text = "Cancel"
            self._concatenate_batch_button.tooltip = (
                "Cancel the current batch operation."
            )
        else:
            self._concatenate_batch_button.text = "Batch Concat."
            self._concatenate_batch_button.tooltip = (
                "Concatenate files in the selected directory by iterating"
                " over the remaining files in the directory based on the "
                "number of files selected."
            )

    def _on_batch_button_clicked(self):
        """Handle batch button click - either start or cancel."""
        if self._batch_runner.is_running:
            self._batch_runner.cancel()
            self._set_batch_button_state(running=False)
            self._progress_bar.label = "Cancelled"
        else:
            self.batch_concatenate_files()

    def _init_widgets(self):
        """Initialize widgets."""
        self._save_directory_prefix = LineEdit(
            label="Save Dir. Prefix",
            tooltip="Prefix for the save directories.",
        )
        self._save_directory = FileEdit(
            mode="d",
            tooltip="Directory where images will be saved. \n"
            "Upon selecting the first file, the save directory will be set \n"
            "to the grandparent directory of the first file.",
        )
        self._save_directory_container = Container(
            widgets=[self._save_directory_prefix, self._save_directory],
            layout="horizontal",
        )
        self._default_save_directory = self._save_directory.value
        self._files = FileEdit(
            mode="rm",
            tooltip="Select file(s) to load.",
        )

        self._progress_bar = ProgressBar(label="Progress")
        self._results = TextEdit(label="Info")

    def _init_save_name_container(self):
        """Initialize the save name container."""
        self._save_name_container = Container(layout="horizontal")
        self._save_name = LineEdit(
            label="Save Name",
            tooltip="Name of the saved file. "
            "Proper extension will be added when saved.",
        )
        self._append_scene_button = PushButton(
            label="Append Scene to Name",
        )
        self._save_name_container.extend(
            [self._save_name, self._append_scene_button]
        )

    def _init_open_image_container(self):
        """Initialize the open image container."""
        self._open_image_container = Container(layout="horizontal")
        self._open_image_button = PushButton(label="Open File(s)")
        self._select_next_image_button = PushButton(
            label="Select Next",
            tooltip="Select the next file(s) in the directory. \n"
            "Note that the files are sorted alphabetically and numerically.",
        )
        self._open_image_container.append(self._open_image_button)
        self._open_image_container.append(self._select_next_image_button)

    def _init_concatenate_files_container(self):
        self._concatenate_files_container = Container(
            layout="horizontal",
        )
        self._concatenate_files_button = PushButton(label="Concat. Files")
        self._concatenate_batch_button = PushButton(
            label="Batch Concat.",
            tooltip="Concatenate files in the selected directory by iterating"
            " over the remaing files in the directory based on the number of"
            " files selected. The files are sorted "
            "alphabetically and numerically, which may not be consistent "
            "with your file viewer. But, opening related consecutive files "
            "should work as expected.",
        )
        self._concatenate_files_container.extend(
            [
                self._concatenate_files_button,
                self._concatenate_batch_button,
            ]
        )

    def _init_metadata_container(self):
        self._update_scale = CheckBox(
            value=True,
            label="Scale",
            tooltip="Update the scale when files are selected.",
        )
        self._update_channel_names = CheckBox(
            value=True,
            label="Channel Names",
            tooltip="Update the channel names when files are selected.",
        )
        self._file_options_container = GroupBoxContainer(
            layout="horizontal",
            name="Update Metadata on File Select",
            labels=False,
            label=False,
            widgets=[self._update_scale, self._update_channel_names],
        )

        self._layer_metadata_update_button = PushButton(
            label="Update from Selected Layer"
        )
        self._num_scenes_label = Label(
            label="Num. Scenes: ",
        )
        self._dim_shape = LineEdit(
            label="Dims: ",
            tooltip="Sanity check for available dimensions.",
        )
        self._image_info_container = Container(
            widgets=[self._num_scenes_label, self._dim_shape],
            layout="horizontal",
        )

        self._channel_names = LineEdit(
            label="Channel Name(s)",
            tooltip="Enter channel names as a list. If left blank or the "
            "channel names are not the proper length, then default channel "
            "names will be used.",
        )

        self._scale_tuple = TupleEdit(
            label="Scale, ZYX",
            tooltip="Pixel size, usually in μm",
            value=(0.0000, 1.0000, 1.0000),
            options={"step": 0.0001},
        )
        self._channel_scale_container = Container(
            widgets=[self._channel_names, self._scale_tuple],
        )
        self._scale_layers_button = PushButton(
            label="Scale Layer(s)",
            tooltip="Scale the selected layer(s) based on the given scale.",
        )
        self._metadata_button_container = Container(
            widgets=[
                self._layer_metadata_update_button,
                self._scale_layers_button,
            ],
            layout="horizontal",
        )

        self._metadata_container = GroupBoxContainer(
            layout="vertical",
            name="Metadata",
            widgets=[
                self._file_options_container,
                self._image_info_container,
                self._channel_scale_container,
                self._metadata_button_container,
            ],
            labels=False,
        )

    def _init_scene_container(self):
        """Initialize the scene container, allowing scene saving."""
        self._scene_container = Container(
            layout="horizontal",
            tooltip="Must be in list index format. Ex: [0, 1, 2] or [5:10]",
        )
        self._scenes_to_extract = LineEdit(
            tooltip="Enter the scenes to extract as a list. If left blank "
            "then all scenes will be extracted.",
        )
        self._extract_scenes = PushButton(
            label="Extract and Save Scenes",
            tooltip="Extract scenes from a single selected file.",
        )
        self._scene_container.append(self._scenes_to_extract)
        self._scene_container.append(self._extract_scenes)

    def _init_save_layers_container(self):
        """Initialize the container to save images, labels, and shapes."""
        self._save_layers_button = PushButton(
            text="Selected Layers (TIFF)",
            tooltip="Concatenate and save all selected layers as OME-TIFF. "
            "Layers will save to corresponding directories based on the layer "
            "type, e.g. Images, Labels, ShapesAsLabels. Shapes are saved as "
            "labels based on the selected image layer dimensions. If multiple "
            "layer types are selected, then the image will save to Layers.",
        )
        self._export_figure_button = PushButton(
            text="Figure (PNG)",
            tooltip="Export the current canvas figure as a PNG to the Figure "
            "directory. Only works in 2D mode. Use Screenshot for 3D figures. "
            "Crops the figure to the extent of the data, attempting to remove "
            "margins. Increase or decrease scaling in the settings",
        )
        self._export_screenshot_button = PushButton(
            text="Canvas (PNG)",
            tooltip="Export the current canvas screenshot as a PNG to the "
            "Figure directory. Works in 2D and 3D mode. Uses the full canvas "
            "size, including margins. Increase or decrease scaling in the "
            "settings, and also it is possible to override the canvas size.",
        )

        self._save_layers_container = GroupBoxContainer(
            layout="horizontal",
            name="Export",
            labels=None,
        )

        self._save_layers_container.extend(
            [
                self._save_layers_button,
                self._export_figure_button,
                self._export_screenshot_button,
            ]
        )

    def _init_layout(self):
        """Initialize the layout of the widget."""
        self._file_group = GroupBoxContainer(
            widgets=[
                self._files,
                self._open_image_container,
            ],
            name="Opening",
            labels=False,
        )
        self._save_group = GroupBoxContainer(
            widgets=[
                self._save_directory_container,
                self._save_name_container,
                self._concatenate_files_container,
                self._scene_container,
                self._save_layers_container,
                self._progress_bar,
            ],
            name="Saving",
            labels=False,
        )

        self.extend(
            [
                self._file_group,
                self._save_group,
                self._metadata_container,
                self._results,
            ]
        )

    def _connect_events(self):
        """Connect the events of the widgets to respective methods."""
        self._files.changed.connect(self.update_save_directory)
        self._files.changed.connect(self.update_metadata_on_file_select)
        self._append_scene_button.clicked.connect(self.append_scene_to_name)
        self._open_image_button.clicked.connect(self.open_images)
        self._select_next_image_button.clicked.connect(self.select_next_images)

        self._layer_metadata_update_button.clicked.connect(
            self.update_metadata_from_layer
        )
        self._scale_layers_button.clicked.connect(self.rescale_by)

        self._concatenate_files_button.clicked.connect(
            self.save_files_as_ome_tiff
        )
        self._concatenate_batch_button.clicked.connect(
            self._on_batch_button_clicked
        )
        self._extract_scenes.clicked.connect(self.save_scenes_ome_tiff)
        self._save_layers_button.clicked.connect(self.save_layers_as_ome_tiff)
        self._export_figure_button.clicked.connect(self.canvas_export_figure)
        self._export_screenshot_button.clicked.connect(self.canvas_screenshot)
        self._results._on_value_change()

    @property
    def p_sizes(self):
        """Get the physical pixel sizes."""
        from bioio_base.types import PhysicalPixelSizes

        return PhysicalPixelSizes(
            self._scale_tuple.value[0],
            self._scale_tuple.value[1],
            self._scale_tuple.value[2],
        )

    def update_save_directory(self):
        """Update the save directory based on the selected files."""
        if self._save_directory.value == self._default_save_directory:
            self._save_directory.value = self._files.value[0].parent.parent

    def _update_metadata_from_Image(
        self,
        img: BioImage,
        update_channel_names: bool = True,
        update_scale: bool = True,
    ):
        """Update the metadata based on the given image."""
        dims = re.search(r"\[(.*?)\]", str(img.dims)).group(1)
        self._dim_shape.value = dims
        self._num_scenes_label.value = str(len(img.scenes))

        self._squeezed_dims_order = helpers.get_squeezed_dim_order(img)
        dims_tuple = tuple(d for d in self._squeezed_dims_order)
        self._squeezed_dims = img.dims[dims_tuple]

        if update_channel_names:
            self._channel_names.value = repr(helpers.get_channel_names(img))
        if update_scale:
            self._scale_tuple.value = (
                img.physical_pixel_sizes.Z or 1,
                img.physical_pixel_sizes.Y or 1,
                img.physical_pixel_sizes.X or 1,
            )

    def update_metadata_on_file_select(self):
        """Update self._save_name.value and metadata if selected."""
        from ndevio import nImage

        self._save_name.value = str(self._files.value[0].stem)
        img = nImage(self._files.value[0])

        self._update_metadata_from_Image(
            img,
            update_channel_names=self._update_channel_names.value,
            update_scale=self._update_scale.value,
        )

    def append_scene_to_name(self):
        """Append the scene to the save name."""
        if self._viewer.layers.selection.active is not None:
            try:
                img = self._viewer.layers.selection.active.metadata["bioimage"]
                scene = re.sub(r"[^\w\s]", "-", img.current_scene)
                self._save_name.value = f"{self._save_name.value}_{scene}"
            except AttributeError:
                self._results.value = (
                    "Tried to append scene to name, but layer not opened with"
                    " ndevio reader."
                )
        else:
            self._results.value = (
                "Tried to append scene to name, but no layer selected."
                " So the first scene from the first file will be appended."
            )
            from ndevio import nImage

            img = nImage(self._files.value[0])
            scene = re.sub(r"[^\w\s]", "-", img.current_scene)
            self._save_name.value = f"{self._save_name.value}_{scene}"

    def update_metadata_from_layer(self):
        """Update metadata from the selected layer."""
        selected_layer = self._viewer.layers.selection.active
        try:
            img = selected_layer.metadata["bioimage"]
            self._update_metadata_from_Image(img)

        except AttributeError:
            self._results.value = (
                "Tried to update metadata, but no layer selected."
                f'\nAt {time.strftime("%H:%M:%S")}'
            )
        except KeyError:
            scale = selected_layer.scale
            self._scale_tuple.value = (
                scale[-3] if len(scale) >= 3 else 1,
                scale[-2],
                scale[-1],
            )
            self._results.value = (
                "Tried to update metadata, but could only update scale"
                " because layer not opened with ndevio reader."
                f'\nAt {time.strftime("%H:%M:%S")}'
            )

    def open_images(self):
        """Open the selected images in the napari viewer with ndevio."""
        self._viewer.open(self._files.value, plugin="ndevio")

    def select_next_images(self):
        """Open the next set of images in the directory."""
        from natsort import os_sorted

        num_files = self._files.value.__len__()

        first_file = self._files.value[0]
        parent_dir = first_file.parent

        files = list(parent_dir.glob(f"*{first_file.suffix}"))
        files = os_sorted(files)

        idx = files.index(first_file)
        next_files = files[idx + num_files : idx + num_files + num_files]

        if not next_files:
            self._results.value = "No more file sets to select."
            return

        from ndevio import nImage

        img = nImage(next_files[0])

        self._save_name.value = helpers.create_id_string(
            img, next_files[0].stem
        )
        self._files.value = next_files

        self.update_metadata_on_file_select()

    def rescale_by(self):
        """Rescale the selected layers based on the given scale."""
        layers = self._viewer.layers.selection
        scale_tup = self._scale_tuple.value

        for layer in layers:
            scale_len = len(layer.scale)
            layer.scale = scale_tup[-scale_len:]

    def concatenate_layers(
        self,
        layers: Layer | list[Layer],
    ) -> np.ndarray:
        """Concatenate the image data from the selected layers."""
        from napari.layers import Shapes as ShapesLayer

        if any(isinstance(layer, ShapesLayer) for layer in layers):
            shape_to_label_dim = self._get_dims_for_shape_layer()

        array_list = []

        for layer in layers:
            if isinstance(layer, ShapesLayer):
                layer_data = layer.to_labels(labels_shape=shape_to_label_dim)
                layer_data = layer_data.astype(np.int16)
            else:
                layer_data = layer.data

            array_list.append(layer_data)

        return np.stack(array_list, axis=0)

    def _get_dims_for_shape_layer(self) -> tuple[int, ...]:
        if self._squeezed_dims is not None:
            return self._squeezed_dims

        from napari.layers import Image as ImageLayer
        from napari.layers import Labels as LabelsLayer

        dim_layer = next(
            (
                layer
                for layer in self._viewer.layers
                if isinstance(layer, ImageLayer | LabelsLayer)
            ),
            None,
        )
        if dim_layer is None:
            raise ValueError(
                "No image or labels present to convert shapes layer."
            )
        label_dim = dim_layer.data.shape
        label_dim = label_dim[:-1] if label_dim[-1] == 3 else label_dim

        return label_dim

    def _get_save_loc(
        self, root_dir: Path, parent: str, file_name: str
    ) -> Path:
        """Get the save location based on the parent directory."""
        save_directory = root_dir / parent
        save_directory.mkdir(parents=False, exist_ok=True)
        return save_directory / file_name

    def _determine_save_directory(self, save_dir: str | None = None) -> str:
        if self._save_directory_prefix.value != "":
            save_dir = f"{self._save_directory_prefix.value}_{save_dir}"
        else:
            save_dir = f"{save_dir}"
        return save_dir

    def save_files_as_ome_tiff(self) -> None:
        """Save the selected files as OME-TIFF with threading."""
        from napari.qt import create_worker

        save_dir = self._determine_save_directory("ConcatenatedImages")
        save_directory = self._save_directory.value / save_dir
        save_name = self._save_name.value

        cnames = self._channel_names.value
        channel_names = ast.literal_eval(cnames) if cnames else None

        self._progress_bar.label = "Concatenating files..."
        self._progress_bar.value = 0
        self._progress_bar.max = 0

        self._concat_worker = create_worker(
            concatenate_and_save_files,
            file_set=(list(self._files.value), save_name),
            save_directory=save_directory,
            channel_names=channel_names,
            p_sizes=self.p_sizes,
        )
        self._concat_worker.returned.connect(self._on_concat_complete)
        self._concat_worker.errored.connect(self._on_concat_error)
        self._concat_worker.start()

    def _on_concat_complete(self, save_path: Path) -> None:
        """Handle completion of file concatenation."""
        self._progress_bar.label = ""
        self._progress_bar.max = 1
        self._progress_bar.value = 1
        self._results.value = (
            f"Saved Concatenated Image: {save_path.name}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _on_concat_error(self, exception: Exception) -> None:
        """Handle error during file concatenation."""
        self._progress_bar.label = "Error"
        self._progress_bar.max = 1
        self._progress_bar.value = 0
        self._results.value = (
            f"Error concatenating files: {exception}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _build_file_sets(self) -> list[tuple[list[Path], str]]:
        """Build list of file sets for batch processing."""
        from natsort import os_sorted

        if not self._files.value:
            return []

        parent_dir = self._files.value[0].parent
        suffix = self._files.value[0].suffix
        num_files = len(self._files.value)

        all_files = os_sorted(list(parent_dir.glob(f"*{suffix}")))

        from ndevio import nImage

        file_sets = []
        for i in range(0, len(all_files), num_files):
            files = all_files[i : i + num_files]
            if len(files) == num_files:
                img = nImage(files[0])
                save_name = helpers.create_id_string(img, files[0].stem)
                file_sets.append((files, save_name))

        return file_sets

    def batch_concatenate_files(self) -> None:
        """Concatenate files in the selected directory."""
        file_sets = self._build_file_sets()

        if not file_sets:
            self._results.value = (
                f'No complete file sets found.\nAt {time.strftime("%H:%M:%S")}'
            )
            return

        cnames = self._channel_names.value
        channel_names = ast.literal_eval(cnames) if cnames else None

        save_dir = self._determine_save_directory("ConcatenatedImages")
        save_directory = self._save_directory.value / save_dir

        self._progress_bar.label = "Starting batch..."
        self._set_batch_button_state(running=True)

        self._batch_runner.run(
            concatenate_and_save_files,
            file_sets,
            save_directory=save_directory,
            channel_names=channel_names,
            p_sizes=self.p_sizes,
            log_file=save_directory / "batch_concatenate.log.txt",
            log_header={
                "Source Directory": str(self._files.value[0].parent),
                "Save Directory": str(save_directory),
                "Files per Set": len(self._files.value),
                "Total Sets": len(file_sets),
            },
            threaded=True,
        )

    def save_scenes_ome_tiff(self) -> None:
        """Save selected scenes as OME-TIFF with threading."""
        from napari.qt import create_worker

        from ndevio import nImage

        file_path = self._files.value[0]
        img = nImage(file_path)

        scenes = self._scenes_to_extract.value
        scenes_list = ast.literal_eval(scenes) if scenes else list(img.scenes)

        save_dir = self._determine_save_directory("ExtractedScenes")
        save_directory = self._save_directory.value / save_dir

        base_save_name = self._save_name.value.split(".")[0]

        cnames = self._channel_names.value
        channel_names = ast.literal_eval(cnames) if cnames else None

        self._progress_bar.label = "Extracting Scenes"
        self._progress_bar.value = 0
        self._progress_bar.max = len(scenes_list)

        self._scene_worker = create_worker(
            extract_and_save_scenes_ome_tiff,
            file_path=file_path,
            save_directory=save_directory,
            scenes=scenes_list,
            channel_names=channel_names,
            p_sizes=self.p_sizes,
            base_save_name=base_save_name,
        )
        self._scene_worker.yielded.connect(self._on_scene_extracted)
        self._scene_worker.finished.connect(
            partial(self._on_scenes_complete, scenes_list)
        )
        self._scene_worker.errored.connect(self._on_scene_error)
        self._scene_worker.start()

    def _on_scene_extracted(self, result: tuple[int, str]) -> None:
        """Handle completion of a single scene extraction."""
        scene_idx, scene_name = result
        self._progress_bar.value = self._progress_bar.value + 1
        self._results.value = (
            f"Extracted scene {scene_idx}: {scene_name}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _on_scenes_complete(self, scenes_list: list, _=None) -> None:
        """Handle completion of all scene extractions."""
        self._progress_bar.label = ""
        self._results.value = (
            f"Saved extracted scenes: {scenes_list}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _on_scene_error(self, exc: Exception) -> None:
        """Handle error during scene extraction."""
        self._progress_bar.label = "Error"
        self._progress_bar.max = 1
        self._progress_bar.value = 0
        self._results.value = (
            f'Error extracting scenes: {exc}\nAt {time.strftime("%H:%M:%S")}'
        )

    def canvas_export_figure(self) -> None:
        """Export the current canvas figure to the save directory."""
        if self._viewer.dims.ndisplay != 2:
            self._results.value = (
                "Exporting Figure only works in 2D mode."
                "\nUse Screenshot for 3D figures."
                f'\nAt {time.strftime("%H:%M:%S")}'
            )
            return

        save_name = f"{self._save_name.value}_figure.png"
        save_path = self._get_save_loc(
            self._save_directory.value,
            "Figures",
            save_name,
        )

        scale = self._settings.ndevio_export.canvas_scale

        self._viewer.export_figure(
            path=str(save_path),
            scale_factor=scale,
        )

        self._results.value = (
            f"Exported canvas figure to Figures directory."
            f"\nSaved as {save_name}"
            f"\nWith scale factor of {scale}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )
        return

    def canvas_screenshot(self) -> None:
        """Export the current canvas screenshot to the save directory."""
        save_name = f"{self._save_name.value}_canvas.png"
        save_path = self._get_save_loc(
            self._save_directory.value, "Figures", save_name
        )

        scale = self._settings.ndevio_export.canvas_scale
        if self._settings.ndevio_export.override_canvas_size:
            canvas_size = self._settings.ndevio_export.canvas_size
        else:
            canvas_size = self._viewer.window._qt_viewer.canvas.size

        self._viewer.screenshot(
            canvas_only=True,
            size=canvas_size,
            scale=scale,
            path=str(save_path),
        )

        self._results.value = (
            f"Exported screenshot of canvas to Figures directory."
            f"\nSaved as {save_name}"
            f"\nWith canvas dimensions of {canvas_size}"
            f"\nWith scale factor of {scale}"
            f'\nAt {time.strftime("%H:%M:%S")}'
        )
        return

    def save_layers_as_ome_tiff(self) -> None:
        """Save the selected layers as OME-TIFF."""
        from napari.qt import create_worker

        layer_data = self.concatenate_layers(
            list(self._viewer.layers.selection)
        )
        layer_types = [
            type(layer).__name__ for layer in self._viewer.layers.selection
        ]

        layer_save_type = (
            "Layers" if len(set(layer_types)) > 1 else layer_types[0]
        )
        layer_save_dir = self._determine_save_directory(layer_save_type)
        layer_save_name = f"{self._save_name.value}.tiff"
        layer_save_loc = self._get_save_loc(
            self._save_directory.value, layer_save_dir, layer_save_name
        )

        if layer_save_type not in ["Shapes", "Labels"]:
            cnames = self._channel_names.value
            channel_names = ast.literal_eval(cnames) if cnames else None
        else:
            channel_names = [layer_save_type]

        if layer_save_type == "Shapes":
            layer_data = layer_data.astype(np.int16)

        elif layer_save_type == "Labels":
            if layer_data.max() > 65535:
                layer_data = layer_data.astype(np.int32)
            else:
                layer_data = layer_data.astype(np.int16)

        if self._squeezed_dims_order:
            dim_order = "C" + self._squeezed_dims_order
        else:
            num_dims = len(layer_data.shape)
            dim_order = "C" + "".join(
                [str(d) for d in "TZYX"[-(num_dims - 1) :]]
            )

        self._layer_save_type = layer_save_type

        self._layer_save_worker = create_worker(
            save_ome_tiff,
            data=layer_data,
            uri=layer_save_loc,
            dim_order=dim_order,
            channel_names=channel_names,
            image_name=self._save_name.value,
            physical_pixel_sizes=self.p_sizes,
        )
        self._layer_save_worker.finished.connect(self._on_layer_save_complete)
        self._layer_save_worker.errored.connect(self._on_layer_save_error)
        self._layer_save_worker.start()

    def _on_layer_save_complete(self, result: None = None) -> None:
        """Handle successful layer save completion."""
        self._results.value = (
            f"Saved {self._layer_save_type}: "
            + str(self._save_name.value)
            + f'\nAt {time.strftime("%H:%M:%S")}'
        )

    def _on_layer_save_error(self, exc: Exception) -> None:
        """Handle layer save error."""
        self._progress_bar.label = "Error"
        self._progress_bar.max = 1
        self._progress_bar.value = 0
        self._results.value = (
            f'Error saving layers: {exc}\nAt {time.strftime("%H:%M:%S")}'
        )
