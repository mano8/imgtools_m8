class ImageFormatInterface:
    """
    Interface for image format handling in image processing tools.
    """

    def load_image(self, file_path: str) -> None:
        """
        Load an image from the specified file path.
        """
        raise NotImplementedError("load_image method must be implemented.")

    def save_image(self, file_path: str) -> None:
        """
        Save the current image to the specified file path.
        """
        raise NotImplementedError("save_image method must be implemented.")

    def get_image_format(self) -> str:
        """
        Get the format of the current image.
        """
        raise NotImplementedError("get_image_format method must be implemented.")
