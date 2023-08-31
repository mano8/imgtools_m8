"""
A helper class for selecting model scales based on image dimensions.

Author: Eli Serra
Copyright: Copyright 2020, Eli Serra
License: Apache 2 License
Version: 1.0.0
"""
import math
import numpy as np
from typing import Optional
from ve_utils.utils import UType as Ut
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "Apache 2"
__status__ = "Production"
__version__ = "1.0.0"


class ModelScaleSelector:
    """
    A helper class for selecting model scales based on image dimensions.
    """

    @staticmethod
    def need_upscale(height: int,
                     width: int,
                     fixed_height: Optional[int] = None,
                     fixed_width: Optional[int] = None
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

        :raises ImgToolsException: If the input size values are not valid integers or less than 1.

        Example:
            >>> ModelScaleSelector.need_upscale(
            >>>     height=250, width=320, fixed_width=350
            >>> )
            >>> True
        """
        result = False
        if not Ut.is_int(height, mini=1) \
                or not Ut.is_int(width, mini=1):
            raise ImgToolsException(
                "Error: Bad image size values."
            )
        if Ut.is_int(fixed_width, mini=1) \
                and Ut.is_int(fixed_height, mini=1) \
                and fixed_width > width \
                and fixed_height > height:
            result = True
        elif Ut.is_int(fixed_height, mini=1) \
                and fixed_height > height:
            result = True
        elif Ut.is_int(fixed_width, mini=1) \
                and fixed_width > width:
            result = True
        return result

    @staticmethod
    def get_model_scale_needed(height: int,
                               width: int,
                               fixed_height: Optional[int] = None,
                               fixed_width: Optional[int] = None
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
        result = 0
        if not Ut.is_int(height, mini=1) \
                or not Ut.is_int(width, mini=1):
            raise ImgToolsException(
                "Error: Bad image size values."
            )
        if Ut.is_int(fixed_height) \
                and Ut.is_int(fixed_width) \
                and fixed_height > height \
                and fixed_width > width:
            scale_w = math.ceil(fixed_width / width)
            scale_h = math.ceil(fixed_height / height)
            result = min(scale_w, scale_h)

        elif Ut.is_int(fixed_width) \
                and fixed_width > width:
            result = math.ceil(fixed_width / width)

        elif Ut.is_int(fixed_height) \
                and fixed_height > height:
            result = math.ceil(fixed_height / height)
        return result

    @staticmethod
    def count_upscale(height: int,
                      width: int,
                      model_scale: int,
                      fixed_height: Optional[int] = None,
                      fixed_width: Optional[int] = None
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
        if not Ut.is_int(height, mini=1) \
                or not Ut.is_int(width, mini=1):
            raise ImgToolsException(
                "Error: Bad image size values."
            )

        if not Ut.is_int(model_scale, mini=1):
            raise ImgToolsException(
                "Error: Bad model scale value. Must be > 0"
            )

        while ModelScaleSelector.need_upscale(
                width=width,
                height=height,
                fixed_width=fixed_width,
                fixed_height=fixed_height):
            width = width * model_scale
            height = height * model_scale
            result += 1
        return result

    @staticmethod
    def get_best_scale_combinations(max_x_scale: int,
                                    available_scales: list,
                                    ) -> list or None:
        """
        Get the best combinations of scaling factors for achieving the target upscale.

        :param max_x_scale: The target upscale value.
        :type max_x_scale: int
        :param available_scales: List of available scaling factors.
        :type available_scales: list

        :return: A list of best combinations of scaling factors, or None if not found.
        :rtype: list or None

        Example:
            >>> max_x_scale = 3
            >>> available_scales = [1, 2, 3, 4]
            >>> ModelScaleSelector.get_best_scale_combinations(max_x_scale, available_scales)
            >>> [[3], [2, 1], [1, 1, 1]]
        """
        best_combination = None
        if Ut.is_int(max_x_scale, mini=1) \
                and Ut.is_list(available_scales, not_null=True):
            total_combinations = ImageToolsHelper.find_all_combinations(
                total=max_x_scale,
                numbers=available_scales
            )
            nb_combinations_min = 0

            for combination in total_combinations:
                nb_scales = len(combination)
                if nb_combinations_min == 0 or nb_scales < nb_combinations_min:
                    nb_combinations_min = nb_scales

            best_combination = [
                x
                for x in total_combinations
                if len(x) <= nb_combinations_min
            ]

        return best_combination

    @staticmethod
    def set_scale_stats(x_scale: int,
                        combination_key: int,
                        combinations: list,
                        actual_scale: int,
                        last_scale: int
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
        if Ut.is_int(x_scale) \
                and Ut.is_list(combinations, not_null=True) \
                and Ut.is_int(combination_key) \
                and Ut.is_int(actual_scale) \
                and Ut.is_int(last_scale):

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
    def get_scale_stats(x_scales: list,
                        combination: list
                        ) -> tuple:
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
        result, stats = None, None
        if Ut.is_list(x_scales, not_null=True) \
                and Ut.is_list(combination, not_null=True):
            result = [[], [], [], []]
            max_loop, loop_counter = 20, 0
            nb_combination, combination_key = len(combination), 0
            last_scale, actual_scale = 0, 0
            for key, x_scale in enumerate(x_scales):
                if x_scale > 0 and x_scale > actual_scale:
                    scale_stats = ModelScaleSelector.set_scale_stats(
                        x_scale=x_scale,
                        combination_key=combination_key,
                        combinations=combination,
                        actual_scale=actual_scale,
                        last_scale=last_scale
                    )
                    combination_scale, combination_key, actual_scale, diff_scale = scale_stats

                    if diff_scale >= 0:
                        result[0].append(combination_scale)
                        result[1].append(1)
                        result[2].append(actual_scale)
                        result[3].append(diff_scale)
                        last_scale = actual_scale
                    else:
                        result[0].append(combination_scale)
                        result[1].append(1)
                        result[2].append(actual_scale)
                        result[3].append(diff_scale)
                        last_scale = actual_scale
                        loop_counter = 0
                        while actual_scale < x_scale:
                            scale_stats = ModelScaleSelector.set_scale_stats(
                                x_scale=x_scale,
                                combination_key=combination_key,
                                combinations=combination,
                                actual_scale=actual_scale,
                                last_scale=last_scale
                            )
                            combination_scale, combination_key, actual_scale, diff_scale = scale_stats
                            result[0].append(combination_scale)
                            result[1].append(1)
                            result[2].append(actual_scale)
                            result[3].append(diff_scale)

                            loop_counter += 1
                            if loop_counter > max_loop:
                                raise ImgToolsException(
                                    "Maximum of 20 scales reached between two fixed sizes. "
                                    "Reduce upscale size, or use higher model scale."
                                )
                            last_scale = actual_scale

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
    def get_scale_combination_stats(x_scales: list,
                                    possibilities: list
                                    ) -> list:
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
        result = None
        if Ut.is_list(x_scales, not_null=True) \
                and Ut.is_list(possibilities, not_null=True):
            result = [[], [], [], []]
            for key, combination in enumerate(possibilities):
                scale_stats, total_stats = ModelScaleSelector.get_scale_stats(
                    x_scales=x_scales,
                    combination=list(combination)
                )
                result[0].append(key)  # combination_key
                result[1].append(total_stats[0])  # max_dif
                result[2].append(total_stats[1])  # max_scale
                result[3].append(total_stats[2])  # total_scale
        return result

    @staticmethod
    def scale_combination_analytics(x_scales: list,
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
        if Ut.is_list(x_scales, not_null=True) \
                and Ut.is_list(possibilities, not_null=True):
            all_stats = ModelScaleSelector.get_scale_combination_stats(
                x_scales=x_scales,
                possibilities=possibilities
            )
            if Ut.is_list(all_stats, not_null=True):
                np_stats = np.array(all_stats)
                min_stat = int(np.argmin(np_stats[1] + np_stats[2] + np_stats[3]))
                key_sel = np_stats[0][min_stat]
                best_combination = possibilities[key_sel]
                # Other way to check all better combinations
                # best_combinations = np.where(
                #     [
                #         (np_stats[1] == np_stats[1].min()) &
                #         (np_stats[2] == np_stats[2].min()) &
                #         (np_stats[3] == np_stats[3].min())
                #     ]
                # )
                result, stats = ModelScaleSelector.get_scale_stats(
                    x_scales=x_scales,
                    combination=list(best_combination)
                )

        return result, stats, best_combination

    @staticmethod
    def format_model_scale_stats(stats: list,
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
            >>> print(formatted_stats)
            >>> [
            >>>     {'x_scale': 2, 'max_dif': 5, 'nb_scale': 2, 'scale': 2, 'actual_scale': 2, 'dif_scale': 2},
            >>>     {'x_scale': 4, 'max_dif': 7, 'nb_scale': 3, 'scale': 4, 'actual_scale': 4, 'dif_scale': 1},
            >>>     {'x_scale': 3, 'max_dif': 6, 'nb_scale': 1, 'scale': 3, 'actual_scale': 3, 'dif_scale': 0}
            >>> ]
        """
        if Ut.is_list(stats, not_null=True) \
                and Ut.is_list(scale_analytics, not_null=True) \
                and Ut.is_list(scale_analytics[0], not_null=True):
            nb_combination = len(scale_analytics[0])
            nb_stats = len(stats)
            if nb_combination == nb_stats:
                for key, data in enumerate(stats):
                    data.update(
                        {
                            'nb_upscale': scale_analytics[1][key],
                            'scale': scale_analytics[0][key],
                            'actual_scale': scale_analytics[2][key],
                            'dif_scale': scale_analytics[3][key],
                        }
                    )
            elif nb_combination > nb_stats:
                for key, actual_scale in enumerate(scale_analytics[2]):
                    nb_stats = len(stats)
                    if key < nb_stats:
                        x_scale = stats[key].get('x_scale')

                        if x_scale <= actual_scale:
                            stats[key].update(
                                {
                                    'nb_upscale': scale_analytics[1][key],
                                    'scale': scale_analytics[0][key],
                                    'actual_scale': scale_analytics[2][key],
                                    'dif_scale': scale_analytics[3][key],
                                }
                            )
                        else:
                            tmp = {
                                'key': -1,
                                'x_scale': actual_scale,
                                'nb_upscale': scale_analytics[1][key],
                                'scale': scale_analytics[0][key],
                                'actual_scale': scale_analytics[2][key],
                                'dif_scale': scale_analytics[3][key],
                            }
                            stats.insert(key, tmp)
                    else:
                        raise ImgToolsException(
                            "Fatal error:  unable to format scale combination statistics. "
                            "Scale statistics out of range"
                        )

            else:
                raise ImgToolsException(
                    "Fatal error:  unable to format scale combination statistics. "
                    "Unexpected statistics rows"
                )
        else:
            raise ImgToolsException(
                "Fatal error:  unable to format scale combination statistics. "
                "Bad parameters."
            )
        return stats

    @staticmethod
    def define_model_scale(upscale_stats: dict,
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
            >>> {
            >>>     'max_x_scale': 10,
            >>>     'stats': [
            >>>         {'key': 0, 'x_scale': 2, 'nb_scale': 0, 'scale': 0, 'actual_scale': 0, 'dif_scale': 0},
            >>>         {'key': 1, 'x_scale': 4, 'nb_scale': 2, 'scale': 2, 'actual_scale': 2, 'dif_scale': 2},
            >>>         {'key': 2, 'x_scale': 6, 'nb_scale': 3, 'scale': 2, 'actual_scale': 4, 'dif_scale': 2}
            >>>     ],
            >>>     'used_scales': [2, 2],
            >>>     'max_dif': 2,
            >>>     'max_scale': 4,
            >>>     'total_scale': 5
            >>> }
        """

        if Ut.is_dict(upscale_stats, not_null=True) \
                and Ut.is_int(upscale_stats.get('max_x_scale'), mini=1) \
                and Ut.is_list(upscale_stats.get('stats'), not_null=True) \
                and Ut.is_list(available_scales, not_null=True):
            max_x_scale = upscale_stats.get('max_x_scale')
            best_combination = ModelScaleSelector.get_best_scale_combinations(
                max_x_scale=max_x_scale,
                available_scales=available_scales
            )

            if Ut.is_list(best_combination, not_null=True):

                x_scales = [x.get('x_scale') for x in upscale_stats.get('stats')]
                combination, stats_apply, best_combination = ModelScaleSelector.scale_combination_analytics(
                    x_scales=x_scales,
                    possibilities=best_combination
                )
                upscale_stats['used_scales'] = list(best_combination)
                upscale_stats.update(
                    {
                        'max_dif': stats_apply[0],
                        'max_scale': stats_apply[1],
                        'total_scale': stats_apply[2],
                    }
                )
                ModelScaleSelector.format_model_scale_stats(
                    stats=upscale_stats.get('stats'),
                    scale_analytics=combination
                )

            return upscale_stats

    @staticmethod
    def get_max_upscale(size: tuple,
                        output_formats: list
                        ) -> dict:
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
        result = None
        if ImageToolsHelper.is_image_size(size) \
                and Ut.is_list(output_formats, not_null=True):
            h, w = size
            result = {
                'max_x_scale': 0,
                'stats': []
            }
            for key, output_format in enumerate(output_formats):
                x_scale = ModelScaleSelector.get_model_scale_needed(
                    width=w,
                    height=h,
                    fixed_width=output_format.get('fixed_width'),
                    fixed_height=output_format.get('fixed_height')
                )
                result['max_x_scale'] = max(result.get('max_x_scale'), x_scale)
                result['stats'].append({
                    'key': key,
                    'x_scale': x_scale
                })
            result['stats'] = sorted(
                result.get('stats'),
                key=lambda d: d['x_scale']
            )
        return result

    @staticmethod
    def get_upscale_stats(size: tuple,
                          output_formats: list,
                          model_scale: int,
                          ) -> dict:
        """
        Get upscale stats from output configuration sizes
        """
        result = None
        h, w = size
        if Ut.is_list(output_formats, not_null=True) \
                and Ut.is_int(model_scale, not_null=True):
            result = {
                'max_x_scale': 0,
                'max_upscale': 0,
                'stats': []
            }
            for key, output_format in enumerate(output_formats):
                fixed_height = output_format.get('fixed_height')
                fixed_width = output_format.get('fixed_width')
                tmp = ModelScaleSelector.count_upscale(
                    width=w,
                    height=h,
                    model_scale=model_scale,
                    fixed_width=fixed_width,
                    fixed_height=fixed_height)
                x_scale = ModelScaleSelector.get_model_scale_needed(
                    width=w,
                    height=h,
                    fixed_width=fixed_width,
                    fixed_height=fixed_height)
                result['max_x_scale'] = max(result.get('max_x_scale'), x_scale)
                result['max_upscale'] = max(result.get('max_upscale'), tmp)
                result['stats'].append({
                    'key': key,
                    'nb_upscale': tmp,
                    'x_scale': x_scale
                })
            result['stats'] = sorted(
                result.get('stats'),
                key=lambda d: d['x_scale']
            )
        return result
