"""
A helper class for selecting model scales based on image dimensions.

Author: Eli Serra
Copyright: Copyright 2020, Eli Serra
License: Apache 2 License
Version: 1.0.0
"""

import math
from typing import Optional

import numpy as np

from imgtools_m8.core.exceptions import ImgToolsException
from imgtools_m8.helper import ImageToolsHelper

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache 2"
__status__ = "Production"
__version__ = "1.0.0"


def _is_valid_pos_int(val: object) -> bool:
    """Return True if val is an integer >= 1."""
    return isinstance(val, int) and val >= 1


def _dim_exceeds(fixed: Optional[int], current: int) -> bool:
    """Return True if fixed is a valid positive int that exceeds current."""
    return _is_valid_pos_int(fixed) and fixed > current  # type: ignore[operator]


class ModelScaleSelector:
    """
    A helper class for selecting model scales based on image dimensions.
    """

    @staticmethod
    def need_upscale(
        height: int,
        width: int,
        fixed_height: Optional[int] = None,
        fixed_width: Optional[int] = None,
    ) -> bool:
        """
        Check if an image needs upscaling based on provided dimensions.

        :param height: The height of the original image.
        :type height: int
        :param width: The width of the original image.
        :type width: int
        :param fixed_height: The fixed height for upscaling. Default is None.
        :type fixed_height: int, optional
        :param fixed_width: The fixed width for upscaling. Default is None.
        :type fixed_width: int, optional
        :return: True if upscaling is needed, False otherwise.
        :rtype: bool

        :raises ImgToolsException:
            If the input size values are not valid integers or less than 1.

        Example:
            >>> ModelScaleSelector.need_upscale(
            >>>     height=250, width=320, fixed_width=350
            >>> )
            >>> True
        """
        if not _is_valid_pos_int(height) or not _is_valid_pos_int(width):
            raise ImgToolsException("Error: Bad image size values.")
        return _dim_exceeds(fixed_height, height) or _dim_exceeds(fixed_width, width)

    @staticmethod
    def _both_dims_need_upscale(
        height: int, width: int, fixed_height: Optional[int], fixed_width: Optional[int]
    ) -> bool:
        """Return True when both fixed dimensions individually exceed the image size."""
        return (
            isinstance(fixed_height, int)
            and isinstance(fixed_width, int)
            and fixed_height > height
            and fixed_width > width
        )

    @staticmethod
    def get_model_scale_needed(
        height: int,
        width: int,
        fixed_height: Optional[int] = None,
        fixed_width: Optional[int] = None,
    ) -> int:
        """
        Get the required model scale for optimal image upscaling.

        :param height: The height of the original image.
        :type height: int
        :param width: The width of the original image.
        :type width: int
        :param fixed_height: The fixed height for the target image scale. Default is None.
        :type fixed_height: int, optional
        :param fixed_width: The fixed width for the target image scale. Default is None.
        :type fixed_width: int, optional

        :return: The optimal model scale factor for upscaling.
        :rtype: int

        :raises ImgToolsException: If the input size values are not valid positive integers.

        Example:
            >>> ModelScaleSelector.get_model_scale_needed(
            >>>     height=250, width=320, fixed_width=350
            >>> )
            >>> 2
        """
        if not _is_valid_pos_int(height) or not _is_valid_pos_int(width):
            raise ImgToolsException("Error: Bad image size values.")
        if ModelScaleSelector._both_dims_need_upscale(
            height, width, fixed_height, fixed_width
        ):
            return min(math.ceil(fixed_width / width), math.ceil(fixed_height / height))  # type: ignore[arg-type, operator]
        if isinstance(fixed_width, int) and fixed_width > width:
            return math.ceil(fixed_width / width)
        if isinstance(fixed_height, int) and fixed_height > height:
            return math.ceil(fixed_height / height)
        return 0

    @staticmethod
    def count_upscale(
        height: int,
        width: int,
        model_scale: int,
        fixed_height: Optional[int] = None,
        fixed_width: Optional[int] = None,
    ) -> int:
        """
        Count the maximum number of upscaling operations needed to reach target dimensions.

        :param height: The height of the original image.
        :type height: int
        :param width: The width of the original image.
        :type width: int
        :param model_scale: The model scale factor for upscaling.
        :type model_scale: int
        :param fixed_height: The fixed height for target dimensions. Default is None.
        :type fixed_height: int, optional
        :param fixed_width: The fixed width for target dimensions. Default is None.
        :type fixed_width: int, optional

        :return: The number of maximum upscaling operations required.
        :rtype: int

        :raises ImgToolsException:
            - If the input size values are not valid positive integers.
            - If the model scale value is not a valid positive integer.

        Example:
            >>> ModelScaleSelector.count_upscale(
            >>>     height=250, width=320, model_scale=2, fixed_width=600
            >>> )
            >>> 3
        """
        result = 0
        if not _is_valid_pos_int(height) or not _is_valid_pos_int(width):
            raise ImgToolsException("Error: Bad image size values.")

        if not _is_valid_pos_int(model_scale):
            raise ImgToolsException("Error: Bad model scale value. Must be > 0")

        while ModelScaleSelector.need_upscale(
            width=width,
            height=height,
            fixed_width=fixed_width,
            fixed_height=fixed_height,
        ):
            width = width * model_scale
            height = height * model_scale
            result += 1
        return result

    @staticmethod
    def get_best_scale_combinations(
        max_x_scale: int,
        available_scales: list,
    ) -> Optional[list]:
        """
        Get the best combinations of scaling factors for achieving the target upscale.

        :param max_x_scale: The target upscale value.
        :type max_x_scale: int
        :param available_scales: List of available scaling factors.
        :type available_scales: list

        :return: A list of best combinations of scaling factors, or None if not found.
        :rtype: Optional[list]

        Example:
            >>> max_x_scale = 3
            >>> available_scales = [1, 2, 3, 4]
            >>> ModelScaleSelector.get_best_scale_combinations(max_x_scale, available_scales)
            >>> [[3], [2, 1], [1, 1, 1]]
        """
        if (
            not _is_valid_pos_int(max_x_scale)
            or not isinstance(available_scales, list)
            or not available_scales
        ):
            return None

        total_combinations = ImageToolsHelper.find_all_combinations(
            total=max_x_scale, numbers=available_scales
        )
        if not isinstance(total_combinations, list) or not total_combinations:
            return []

        min_len = min(len(c) for c in total_combinations)
        return [c for c in total_combinations if len(c) <= min_len]

    @staticmethod
    def set_scale_stats(
        x_scale: int,
        combination_key: int,
        combinations: list,
        actual_scale: int,
        last_scale: int,
    ) -> tuple:
        """
        Calculate the scale statistics for the upscale process.

        :param x_scale: The target upscale value.
        :type x_scale: int
        :param combination_key: The current index of the combination being processed.
        :type combination_key: int
        :param combinations: The list of scaling factor combinations.
        :type combinations: list
        :param actual_scale: The current accumulated scale.
        :type actual_scale: int
        :param last_scale: The last scale factor used.
        :type last_scale: int

        :return: A tuple containing the calculated values:
                 - combination_scale: The scale factor of the current combination.
                 - combination_key: The updated combination index.
                 - actual_scale: The updated accumulated scale.
                 - diff_scale: The difference between the accumulated scale and the target upscale.
        :rtype: tuple

        :raises ImgToolsException: If the arguments are not valid.

        Example:
            >>> x_scale = 5
            >>> combination_key = 0
            >>> combinations = [2, 1, 3]
            >>> actual_scale = 0
            >>> last_scale = 3
            >>> ModelScaleSelector.set_scale_stats(x_scale, combination_key, combinations, actual_scale, last_scale)
            >>> (2, 1, 2, 3)
        """
        scalars_ok = (
            isinstance(x_scale, int)
            and isinstance(combination_key, int)
            and isinstance(actual_scale, int)
            and isinstance(last_scale, int)
        )
        if scalars_ok and isinstance(combinations, list) and combinations:
            nb_combination = len(combinations)
            if combination_key < nb_combination:
                combination_scale = combinations[combination_key]
                combination_key += 1

                actual_scale += combination_scale

                diff_scale = actual_scale - x_scale

            else:
                raise ImgToolsException(
                    "Fatal error:  unable to set scale combination statistics. Scale combination out of range"
                )
        else:
            raise ImgToolsException(
                "Fatal error:  unable to set scale combination statistics. Bad arguments"
            )

        return combination_scale, combination_key, actual_scale, diff_scale

    @staticmethod
    def _append_scale_entry(
        result: list,
        combination_scale: int,
        actual_scale: int,
        diff_scale: int,
    ) -> None:
        """Append one scale step to the running result lists."""
        result[0].append(combination_scale)
        result[1].append(1)
        result[2].append(actual_scale)
        result[3].append(diff_scale)

    @staticmethod
    def _fill_until_reached(
        x_scale: int,
        combination_key: int,
        combination: list,
        actual_scale: int,
        result: list,
    ) -> tuple:
        """Keep consuming combination entries until actual_scale >= x_scale."""
        max_loop = 20
        loop_counter = 0
        last_scale = actual_scale  # always equal at every call site
        while actual_scale < x_scale:
            combination_scale, combination_key, actual_scale, diff_scale = (
                ModelScaleSelector.set_scale_stats(
                    x_scale=x_scale,
                    combination_key=combination_key,
                    combinations=combination,
                    actual_scale=actual_scale,
                    last_scale=last_scale,
                )
            )
            ModelScaleSelector._append_scale_entry(
                result, combination_scale, actual_scale, diff_scale
            )
            loop_counter += 1
            if loop_counter > max_loop:
                raise ImgToolsException(
                    "Maximum of 20 scales reached between two fixed sizes. "
                    "Reduce upscale size, or use higher model scale."
                )
            last_scale = actual_scale
        return combination_key, actual_scale, last_scale

    @staticmethod
    def get_scale_stats(x_scales: list, combination: list) -> tuple:
        """
        Calculate the scale statistics for the upscale process.

        :param x_scales: A list of target upscale values.
        :type x_scales: list[int]
        :param combination: A list of scaling factor combinations.
        :type combination: list[int]

        :return: A tuple containing two lists:
                 - The first list contains the calculated scale factors for each target upscale.
                 - The second list contains the maximum difference, maximum scale, and total scale.
        :rtype: tuple[list[int], list[int]]

        :raises ImgToolsException:
            If the maximum number of iterations is reached.

        Example:
            >>> x_scales = [5, 7, 10]
            >>> combination = [2, 3]
            >>> ModelScaleSelector.get_scale_stats(x_scales, combination)
            (
                [[2, 2, 3, 3, 3], [3, 3, 2, 2, 2], [2, 3, 6, 9, 12], [-1, 0, 2, 5, 8]],
                [8, 12, 13]
            )
        """
        result: Optional[list[list[int]]] = None
        stats: Optional[list[int]] = None
        if (
            not isinstance(x_scales, list)
            or not x_scales
            or not isinstance(combination, list)
            or not combination
        ):
            return result, stats  # pragma: no cover

        result = [[], [], [], []]
        combination_key = 0
        last_scale, actual_scale = 0, 0

        for x_scale in x_scales:
            if x_scale > 0 and x_scale > actual_scale:
                combination_scale, combination_key, actual_scale, diff_scale = (
                    ModelScaleSelector.set_scale_stats(
                        x_scale=x_scale,
                        combination_key=combination_key,
                        combinations=combination,
                        actual_scale=actual_scale,
                        last_scale=last_scale,
                    )
                )
                ModelScaleSelector._append_scale_entry(
                    result, combination_scale, actual_scale, diff_scale
                )
                last_scale = actual_scale
                if diff_scale < 0:
                    combination_key, actual_scale, last_scale = (
                        ModelScaleSelector._fill_until_reached(
                            x_scale,
                            combination_key,
                            combination,
                            actual_scale,
                            result,
                        )
                    )
            else:
                result[0].append(0)
                result[1].append(0)
                result[2].append(actual_scale)
                result[3].append(actual_scale - x_scale)

        max_dif = max(result[3])
        max_scale = max(result[2])
        total_scale = sum(result[1])
        stats = [max_dif, max_scale, total_scale]
        return result, stats

    @staticmethod
    def get_scale_combination_stats(x_scales: list, possibilities: list) -> list:
        """
        Calculate scale combination statistics for different possibilities.

        :param x_scales: A list of target upscale values.
        :type x_scales: list
        :param possibilities: A list of scaling factor combinations.
        :type possibilities: list

        :return: A list containing combination statistics, where each element is a list with:
                 - The combination key.
                 - The maximum difference in scale.
                 - The maximum scale achieved.
                 - The total scale achieved.
        :rtype: list

        Example:
            >>> x_scales = [5, 7, 10]
            >>> possibilities = [[2, 3], [3, 4], [2, 2, 2]]
            >>> ModelScaleSelector.get_scale_combination_stats(x_scales, possibilities)
            >>> [
            >>>     [0, 8, 12, 13],
            >>>     [1, 5, 11, 14],
            >>>     [2, 0, 10, 15]
            >>> ]
        """
        result: Optional[list[list[int]]] = None
        if (
            isinstance(x_scales, list)
            and x_scales
            and isinstance(possibilities, list)
            and possibilities
        ):
            result = [[], [], [], []]
            for key, combination in enumerate(possibilities):
                _, total_stats = ModelScaleSelector.get_scale_stats(
                    x_scales=x_scales, combination=list(combination)
                )
                result[0].append(key)  # combination_key
                result[1].append(total_stats[0])  # max_dif
                result[2].append(total_stats[1])  # max_scale
                result[3].append(total_stats[2])  # total_scale
        return result  # type: ignore[return-value]

    @staticmethod
    def scale_combination_analytics(
        x_scales: list,
        possibilities: list,
    ) -> tuple:
        """
        Perform analytics on different scale combination possibilities.

        :param x_scales: A list of target upscale values.
        :type x_scales: list
        :param possibilities: A list of scaling factor combinations.
        :type possibilities: list

        :return: A tuple containing the following elements:
                 - Combination statistics for the best combination.
                 - Stats for the best combination, including max difference, max scale, and total scale achieved.
                 - The best combination of scaling factors.
        :rtype: tuple

        Example:
            >>> x_scales = [5, 7, 10]
            >>> possibilities = [[2, 3], [3, 4], [2, 2, 2]]
            >>> ModelScaleSelector.scale_combination_analytics(x_scales, possibilities)
            >>> (
            >>>     [2, 0, 10, 15],
            >>>     [0, 10, 15],
            >>>     [2, 2, 2]
            >>> )
        """
        result, stats, best_combination = None, None, None
        if (
            isinstance(x_scales, list)
            and x_scales
            and isinstance(possibilities, list)
            and possibilities
        ):
            all_stats = ModelScaleSelector.get_scale_combination_stats(
                x_scales=x_scales, possibilities=possibilities
            )
            if isinstance(all_stats, list) and all_stats:
                np_stats = np.array(all_stats)
                min_stat = int(np.argmin(np_stats[1] + np_stats[2] + np_stats[3]))
                key_sel = np_stats[0][min_stat]
                best_combination = possibilities[key_sel]
                result, stats = ModelScaleSelector.get_scale_stats(
                    x_scales=x_scales, combination=list(best_combination)
                )

        return result, stats, best_combination

    @staticmethod
    def _apply_format_stats(stats: list, scale_analytics: list) -> None:
        """Apply scale analytics to stats list (same-length case)."""
        for key, data in enumerate(stats):
            data.update(
                {
                    "nb_upscale": scale_analytics[1][key],
                    "scale": scale_analytics[0][key],
                    "actual_scale": scale_analytics[2][key],
                    "dif_scale": scale_analytics[3][key],
                }
            )

    @staticmethod
    def _apply_extended_format_stats(stats: list, scale_analytics: list) -> None:
        """Apply scale analytics when combination has more entries than stats."""
        for key, actual_scale in enumerate(scale_analytics[2]):
            nb_stats = len(stats)
            if key >= nb_stats:
                raise ImgToolsException(
                    "Fatal error:  unable to format scale combination statistics. "
                    "Scale statistics out of range"
                )
            x_scale = stats[key].get("x_scale")
            entry = {
                "nb_upscale": scale_analytics[1][key],
                "scale": scale_analytics[0][key],
                "actual_scale": scale_analytics[2][key],
                "dif_scale": scale_analytics[3][key],
            }
            if x_scale <= actual_scale:
                stats[key].update(entry)
            else:
                stats.insert(key, {"key": -1, "x_scale": actual_scale, **entry})

    @staticmethod
    def format_model_scale_stats(
        stats: list,
        scale_analytics: list,
    ) -> list:
        """
        Format model scale statistics with additional scale analytics.

        :param stats: The original scale statistics.
        :type stats: list
        :param scale_analytics: The scale analytics computed using ModelScaleSelector methods.
        :type scale_analytics: list

        :return: Formatted scale statistics including additional scale analytics.
        :rtype: list

        :raises ImgToolsException:
            If the provided parameters are not valid or have unexpected structures.

        Example:
            >>> original_stats = [
            >>>     {'x_scale': 2, 'max_dif': 5},
            >>>     {'x_scale': 4, 'max_dif': 7},
            >>>     {'x_scale': 3, 'max_dif': 6}
            >>> ]
            >>> scale_analytics = [
            >>>     [2, 4, 3],
            >>>     [2, 3, 1],
            >>>     [4, 5, 3],
            >>>     [5, 2, 3]
            >>> ]
            >>> formatted_stats = ModelScaleSelector.format_model_scale_stats(
            >>>     stats=original_stats,
            >>>     scale_analytics=scale_analytics
            >>> )
        """
        analytics_valid = (
            isinstance(scale_analytics, list)
            and scale_analytics
            and isinstance(scale_analytics[0], list)
            and scale_analytics[0]
        )
        if not (isinstance(stats, list) and stats and analytics_valid):
            raise ImgToolsException(
                "Fatal error:  unable to format scale combination statistics. "
                "Bad parameters."
            )

        nb_combination = len(scale_analytics[0])
        nb_stats = len(stats)

        if nb_combination == nb_stats:
            ModelScaleSelector._apply_format_stats(stats, scale_analytics)
        elif nb_combination > nb_stats:
            ModelScaleSelector._apply_extended_format_stats(stats, scale_analytics)
        else:
            raise ImgToolsException(
                "Fatal error:  unable to format scale combination statistics. "
                "Unexpected statistics rows"
            )
        return stats

    @staticmethod
    def _is_valid_upscale_stats_input(
        upscale_stats: dict, available_scales: list
    ) -> bool:
        """Return True when upscale_stats and available_scales have the required fields."""
        max_x = upscale_stats.get("max_x_scale")
        stats = upscale_stats.get("stats")
        return (
            _is_valid_pos_int(max_x)
            and isinstance(stats, list)
            and bool(stats)
            and isinstance(available_scales, list)
            and bool(available_scales)
        )

    @staticmethod
    def _apply_scale_analytics(
        upscale_stats: dict, stats_val: list, best_combination: list
    ) -> None:
        """Run scale combination analytics and write results back into upscale_stats."""
        x_scales = [x.get("x_scale") for x in stats_val]
        combination, stats_apply, best_combination = (
            ModelScaleSelector.scale_combination_analytics(
                x_scales=x_scales, possibilities=best_combination
            )
        )
        if isinstance(stats_apply, list) and len(stats_apply) >= 3:
            upscale_stats["used_scales"] = list(best_combination)
            upscale_stats.update(
                {
                    "max_dif": stats_apply[0],
                    "max_scale": stats_apply[1],
                    "total_scale": stats_apply[2],
                }
            )
        if isinstance(combination, list):
            ModelScaleSelector.format_model_scale_stats(
                stats=stats_val, scale_analytics=combination
            )

    @staticmethod
    def define_model_scale(
        upscale_stats: dict,
        available_scales: list,
    ) -> dict:
        """
        Define the model scale based on upscale statistics and available scaling factors.

        :param upscale_stats: A dictionary containing upscale statistics.
        :type upscale_stats: dict
        :param available_scales: List of available scaling factors.
        :type available_scales: list

        :return: The updated upscale_stats dictionary with the defined model scale.
        :rtype: dict

        Example:
            >>> upscale_stats = {
            >>>     'max_x_scale': 10,
            >>>     'stats': [
            >>>         {'key': 0, 'x_scale': 2},
            >>>         {'key': 1, 'x_scale': 4},
            >>>         {'key': 2, 'x_scale': 6}
            >>>     ]
            >>> }
            >>> available_scales = [1, 2, 3, 4, 5, 6]
            >>> ModelScaleSelector.define_model_scale(upscale_stats, available_scales)
        """
        if not isinstance(upscale_stats, dict) or not upscale_stats:
            return upscale_stats  # pragma: no cover
        if not ModelScaleSelector._is_valid_upscale_stats_input(
            upscale_stats, available_scales
        ):
            return upscale_stats  # pragma: no cover
        max_x_scale_val = upscale_stats.get("max_x_scale")
        stats_val = upscale_stats.get("stats")
        best_combination = ModelScaleSelector.get_best_scale_combinations(
            max_x_scale=max_x_scale_val,  # type: ignore[arg-type]
            available_scales=available_scales,
        )
        if not isinstance(best_combination, list) or not best_combination:
            return upscale_stats  # pragma: no cover
        ModelScaleSelector._apply_scale_analytics(
            upscale_stats,
            stats_val,  # type: ignore[arg-type]
            best_combination,
        )
        return upscale_stats

    @staticmethod
    def get_max_upscale(size: tuple, output_formats: list) -> Optional[dict]:
        """
        Get the maximum upscale needed to process the image.

        :param size: The original image size as a tuple (height, width).
        :type size: tuple
        :param output_formats: List of output formats containing desired dimensions.
        :type output_formats: list[dict]

        :return: A dictionary containing the maximum x-scale needed and corresponding statistics.
        :rtype: dict

        :raises ImgToolsException:
            If the image size is not a valid tuple of positive integers.
            If the output formats list is empty or not valid.

        Example:
            >>> size = (120, 160)
            >>> output_formats = [{'fixed_width': 200}, {'fixed_width': 300}]
            >>> ModelScaleSelector.get_max_upscale(size, output_formats)
            {'max_x_scale': 2, 'stats': [{'key': 0, 'x_scale': 2}, {'key': 1, 'x_scale': 3}]}
        """
        result: Optional[dict] = None
        if (
            ImageToolsHelper.is_image_size(size)
            and isinstance(output_formats, list)
            and output_formats
        ):
            h, w = size
            max_x: int = 0
            stats_list: list[dict] = []
            for key, output_format in enumerate(output_formats):
                x_scale = ModelScaleSelector.get_model_scale_needed(
                    width=w,
                    height=h,
                    fixed_width=output_format.get("fixed_width"),
                    fixed_height=output_format.get("fixed_height"),
                )
                max_x = max(max_x, x_scale)
                stats_list.append({"key": key, "x_scale": x_scale})
            result = {
                "max_x_scale": max_x,
                "stats": sorted(stats_list, key=lambda d: d["x_scale"]),
            }
        return result

    @staticmethod
    def get_upscale_stats(
        size: tuple,
        output_formats: list,
        model_scale: int,
    ) -> Optional[dict]:
        """
        Get upscale stats from output configuration sizes
        """
        result: Optional[dict] = None
        h, w = size
        if (
            isinstance(output_formats, list)
            and output_formats
            and isinstance(model_scale, int)
        ):
            max_x: int = 0
            max_up: int = 0
            stats_list: list[dict] = []
            for key, output_format in enumerate(output_formats):
                fixed_height = output_format.get("fixed_height")
                fixed_width = output_format.get("fixed_width")
                tmp = ModelScaleSelector.count_upscale(
                    width=w,
                    height=h,
                    model_scale=model_scale,
                    fixed_width=fixed_width,
                    fixed_height=fixed_height,
                )
                x_scale = ModelScaleSelector.get_model_scale_needed(
                    width=w,
                    height=h,
                    fixed_width=fixed_width,
                    fixed_height=fixed_height,
                )
                max_x = max(max_x, x_scale)
                max_up = max(max_up, tmp)
                stats_list.append({"key": key, "nb_upscale": tmp, "x_scale": x_scale})
            result = {
                "max_x_scale": max_x,
                "max_upscale": max_up,
                "stats": sorted(stats_list, key=lambda d: d["x_scale"]),
            }
        return result
