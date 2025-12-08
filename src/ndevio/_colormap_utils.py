"""Colormap utilities for ndevio.

This module provides colormap cycles for
multichannel image display.
"""

SINGLE_CHANNEL_COLORMAP = 'gray'

TWO_CHANNEL_CYCLE = ['magenta', 'green']

MULTI_CHANNEL_CYCLE = ['cyan', 'magenta', 'yellow', 'blue', 'green', 'red']

RGB = ['red', 'green', 'blue']


def get_colormap_for_channel(channel_idx: int, n_channels: int) -> str:
    """
    Get colormap for a channel based on napari's defaults.

    - 1 channel → gray
    - 2 channels → magenta, green (TWO_CHANNEL_CYCLE)
    - 3+ channels → cycles through MULTI_CHANNEL_CYCLE (CMYBGR)

    Parameters
    ----------
    channel_idx : int
        Index of the channel (0-based).
    n_channels : int
        Total number of channels in the image.

    Returns
    -------
    str
        Colormap name.

    """
    if n_channels == 1:
        return SINGLE_CHANNEL_COLORMAP
    elif n_channels == 2:
        return TWO_CHANNEL_CYCLE[channel_idx % len(TWO_CHANNEL_CYCLE)]
    else:
        return MULTI_CHANNEL_CYCLE[channel_idx % len(MULTI_CHANNEL_CYCLE)]


__all__ = [
    'SINGLE_CHANNEL_COLORMAP',
    'TWO_CHANNEL_CYCLE',
    'MULTI_CHANNEL_CYCLE',
    'RGB',
    'get_colormap_for_channel',
]
