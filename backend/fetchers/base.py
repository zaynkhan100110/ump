"""
Base fetcher class for all media source extractors.
Every concrete fetcher must implement the `fetch_formats` method.
"""

class BaseFetcher:
    """
    Abstract base class for fetching available media formats from a given URL.

    Subclasses must override the `fetch_formats` method to return a list
    of format dictionaries.
    """

    def fetch_formats(self, url):
        """
        Fetch available formats for a given media URL.

        Parameters
        ----------
        url : str
            The media URL to extract formats from.

        Returns
        -------
        list of dict
            A list of format dictionaries, each containing at least:
            - format_id (str): unique identifier for the format
            - url (str, optional): direct download URL if known
            - ext (str): file extension, e.g. 'mp4', 'm3u8'
            - quality (str): human‑readable quality label
            - has_video (bool): whether the format contains video
            - has_audio (bool): whether the format contains audio
            - size (int, optional): file size in bytes
            - height (int, optional): video height in pixels
            - width (int, optional): video width in pixels
            - fps (int, optional): frames per second
            - note (str, optional): additional information

        Raises
        ------
        NotImplementedError
            If the subclass does not implement this method.
        """
        raise NotImplementedError(
            "Subclasses must implement fetch_formats(url)"
        )