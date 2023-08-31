"""
ImageToolsHelper unittest class.

Use pytest package.
"""
import pytest
from imgtools_m8.helper import ImageToolsHelper
from imgtools_m8.model_scale_selector import ModelScaleSelector
from imgtools_m8.exceptions import ImgToolsException

__author__ = "Eli Serra"
__copyright__ = "Copyright 2020, Eli Serra"
__deprecated__ = False
__license__ = "MIT"
__status__ = "Production"
__version__ = "1.0.0"


class TestModelScaleSelector:

    @staticmethod
    def test_need_upscale():
        """Test need_upscale method"""
        args = [
            {'width': 22, 'height': 23, 'fixed_width': 25},
            {'width': 22, 'height': 23, 'fixed_height': 25},
            {'width': 22, 'height': 23, 'fixed_width': 25, 'fixed_height': 25},
        ]
        for params in args:
            test = ModelScaleSelector.need_upscale(**params)
            assert test is True

        args = [
            {'width': 22, 'height': 23},
            {'width': 22, 'height': 23, 'fixed_width': 18},
            {'width': 22, 'height': 23, 'fixed_height': 18},
            {'width': 22, 'height': 23, 'fixed_width': 15, 'fixed_height': 18},
        ]
        for params in args:
            test = ModelScaleSelector.need_upscale(**params)
            assert test is False

        args = [
            {'width': 0, 'height': 23},
            {'width': 22, 'height': 0},
            {'width': -1, 'height': 23},
            {'width': 22, 'height': -1}
        ]
        for params in args:
            with pytest.raises(ImgToolsException):
                ModelScaleSelector.need_upscale(**params)

    @staticmethod
    def test_get_model_scale_needed():
        """Test get_model_scale_needed method"""
        args = [
            {'height': 200, 'width': 400, 'fixed_width': 1900},
            {'height': 200, 'width': 500, 'fixed_width': 1600, 'fixed_height': 1600},
            {'height': 200, 'width': 300, 'fixed_width': 1200, 'fixed_height': 800},
            {'height': 200, 'width': 300, 'fixed_width': 200, 'fixed_height': 350},
            {'height': 200, 'width': 500, 'fixed_height': 600},
            {'height': 200, 'width': 400, 'fixed_width': 200}
        ]
        results = []
        for params in args:
            tmp = ModelScaleSelector.get_model_scale_needed(**params)
            results.append(tmp)
        assert results == [5, 4, 4, 2, 3, 0]
        with pytest.raises(ImgToolsException):
            ModelScaleSelector.get_model_scale_needed(
                width=0,
                height=22
            )

        with pytest.raises(ImgToolsException):
            ModelScaleSelector.get_model_scale_needed(
                width=22,
                height=0
            )

    @staticmethod
    def test_count_upscale():
        """Test count_upscale method"""
        upscale_formats = [
            {'height': 200, 'width': 400, 'model_scale': 3, 'fixed_width': 1900},
            {'height': 200, 'width': 500, 'model_scale': 2, 'fixed_height': 1600},
            {'height': 200, 'width': 300, 'model_scale': 4, 'fixed_width': 1200, 'fixed_height': 800},
            {'height': 200, 'width': 300, 'model_scale': 2, 'fixed_width': 200, 'fixed_height': 350},
            {'height': 200, 'width': 500, 'model_scale': 2, 'fixed_height': 600},
            {'height': 200, 'width': 400, 'model_scale': 2, 'fixed_width': 200}
        ]
        results = []
        for params in upscale_formats:
            tmp = ModelScaleSelector.count_upscale(**params)
            results.append(tmp)
        assert results == [2, 3, 1, 1, 2, 0]
        with pytest.raises(ImgToolsException):
            ModelScaleSelector.count_upscale(
                width=0,
                height=22,
                model_scale=2
            )

        with pytest.raises(ImgToolsException):
            ModelScaleSelector.count_upscale(
                width=22,
                height=0,
                model_scale=2
            )

        with pytest.raises(ImgToolsException):
            ModelScaleSelector.count_upscale(
                width=22,
                height=22,
                model_scale=0
            )

    @staticmethod
    def test_get_best_scale_combination():
        """Test get_best_scale_combinations method"""
        upscale_formats = [
            {'max_x_scale': -1, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 0, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 2, 'available_scales': []},
            {'max_x_scale': 1, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 2, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 3, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 4, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 5, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 7, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 8, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 9, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 10, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 11, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 13, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 15, 'available_scales': [2, 3, 4]},
            {'max_x_scale': 19, 'available_scales': [2, 3, 4]},
        ]
        results = []
        for params in upscale_formats:
            tmp = ModelScaleSelector.get_best_scale_combinations(**params)
            results.append(tmp)
        assert results == [
            None, None, None, [],
            [[2]], [[3]], [[4]],
            [[3, 2], [2, 3]], [[4, 3], [3, 4]],
            [[4, 4]], [[4, 3, 2], [3, 4, 2], [4, 2, 3], [3, 3, 3], [2, 4, 3], [3, 2, 4], [2, 3, 4]],
            [[4, 4, 2], [4, 3, 3], [3, 4, 3], [4, 2, 4], [3, 3, 4], [2, 4, 4]],
            [[4, 4, 3], [4, 3, 4], [3, 4, 4]],
            [
                [4, 4, 3, 2], [4, 3, 4, 2], [3, 4, 4, 2], [4, 4, 2, 3],
                [4, 3, 3, 3], [3, 4, 3, 3], [4, 2, 4, 3], [3, 3, 4, 3],
                [2, 4, 4, 3], [4, 3, 2, 4], [3, 4, 2, 4], [4, 2, 3, 4],
                [3, 3, 3, 4], [2, 4, 3, 4], [3, 2, 4, 4], [2, 3, 4, 4]
            ],
            [[4, 4, 4, 3], [4, 4, 3, 4], [4, 3, 4, 4], [3, 4, 4, 4]],
            [[4, 4, 4, 4, 3], [4, 4, 4, 3, 4], [4, 4, 3, 4, 4], [4, 3, 4, 4, 4], [3, 4, 4, 4, 4]]]

    @staticmethod
    def test_set_scale_stats():
        """Test set_scale_stats method"""
        args = [
            {'x_scale': 2, 'combination_key': 0, 'combinations': [2, 3, 4], 'actual_scale': 2, 'last_scale': 0},
            {'x_scale': 6, 'combination_key': 1, 'combinations': [2, 3, 4], 'actual_scale': 6, 'last_scale': 2},
            {'x_scale': 6, 'combination_key': 1, 'combinations': [2, 3, 4], 'actual_scale': 3, 'last_scale': 6},
        ]
        results = []
        for params in args:
            tmp = ModelScaleSelector.set_scale_stats(**params)
            results.append(tmp)
        assert results == [(2, 1, 4, 2), (3, 2, 9, 3), (3, 2, 6, 0)]

        args = [
            {'x_scale': 2, 'combination_key': 5, 'combinations': [2, 3, 4], 'actual_scale': 2, 'last_scale': 0},
            {'x_scale': 6, 'combination_key': 1, 'combinations': [], 'actual_scale': 6, 'last_scale': 2},
        ]
        for params in args:

            with pytest.raises(ImgToolsException):
                ModelScaleSelector.set_scale_stats(**params)

    @staticmethod
    def test_get_scale_stats():
        """Test set_scale_stats method"""
        args = [
            {'x_scales': [4, 8], 'combination': [4, 4]},
            {'x_scales': [2, 5], 'combination': [2, 3]},
        ]
        results = []
        for params in args:
            tmp = ModelScaleSelector.get_scale_stats(**params)
            results.append(tmp)
        assert results == [
            ([[4, 4], [1, 1], [4, 8], [0, 0]], [0, 8, 2]),
            ([[2, 3], [1, 1], [2, 5], [0, 0]], [0, 5, 2])
        ]

        args = [
            {'x_scales': [4, 50], 'combination': [2 for x in range(2,50, 2)]}
        ]
        for params in args:
            with pytest.raises(ImgToolsException):
                ModelScaleSelector.get_scale_stats(**params)

    @staticmethod
    def test_scale_combination_analytics():
        """Test scale_combination_analytics method"""
        args = [
            {
                'x_scales': [0, 2, 5],
                'possibilities': ModelScaleSelector.get_best_scale_combinations(
                    max_x_scale=5,
                    available_scales=[2, 3, 4]
                )
            },
            {
                'x_scales': [0, 3, 5],
                'possibilities': ModelScaleSelector.get_best_scale_combinations(
                    max_x_scale=5,
                    available_scales=[2, 3, 4]
                )
            },
            {
                'x_scales': [0, 4, 8],
                'possibilities': ModelScaleSelector.get_best_scale_combinations(
                    max_x_scale=8,
                    available_scales=[2, 3, 4]
                )
            },
            {
                'x_scales': [0, 2, 8, 15],
                'possibilities': ModelScaleSelector.get_best_scale_combinations(
                    max_x_scale=15,
                    available_scales=[2, 3, 4]
                )
            },
            {
                'x_scales': [0, 2, 4, 5, 8, 14],
                'possibilities': ModelScaleSelector.get_best_scale_combinations(
                    max_x_scale=14,
                    available_scales=[2, 3, 4]
                )
            },
        ]
        results = []
        for params in args:
            scale = ModelScaleSelector.scale_combination_analytics(**params)
            results.append(scale)
        assert results[0][2] == [2, 3]
        assert results[1][2] == [3, 2]
        assert results[2][2] == [4, 4]
        assert results[3][2] == [4, 4, 4, 3]
        assert results[4][2] == [4, 3, 3, 4]

    @staticmethod
    def test_format_model_scale_stats():
        """Test format_model_scale_stats method"""
        args = [
            {
                'stats': [
                    {'key': 3, 'x_scale': 0},
                    {'key': 2, 'x_scale': 2},
                    {'key': 1, 'x_scale': 5},
                ],
                'scale_analytics': [
                    [0, 2, 3],
                    [0, 1, 1],
                    [0, 2, 5],
                    [0, 0, 0]
                ]
            },
            {
                'stats': [
                    {'key': 3, 'x_scale': 0},
                    {'key': 2, 'x_scale': 5},
                    {'key': 1, 'x_scale': 10},
                ],
                'scale_analytics': [
                    [0, 4, 4, 2],
                    [0, 1, 1, 1],
                    [0, 4, 8, 10],
                    [0, 0, 3, 0]
                ]
            }
        ]
        results = []
        for params in args:
            tmp = ModelScaleSelector.format_model_scale_stats(**params)
            results.append(tmp)

        assert results == [
            [
                {'key': 3, 'x_scale': 0, 'nb_upscale': 0, 'scale': 0, 'actual_scale': 0, 'dif_scale': 0},
                {'key': 2, 'x_scale': 2, 'nb_upscale': 1, 'scale': 2, 'actual_scale': 2, 'dif_scale': 0},
                {'key': 1, 'x_scale': 5, 'nb_upscale': 1, 'scale': 3, 'actual_scale': 5, 'dif_scale': 0}
            ],
            [
                {'key': 3, 'x_scale': 0, 'nb_upscale': 0, 'scale': 0, 'actual_scale': 0, 'dif_scale': 0},
                {'key': -1, 'x_scale': 4, 'nb_upscale': 1, 'scale': 4, 'actual_scale': 4, 'dif_scale': 0},
                {'key': 2, 'x_scale': 5, 'nb_upscale': 1, 'scale': 4, 'actual_scale': 8, 'dif_scale': 3},
                {'key': 1, 'x_scale': 10, 'nb_upscale': 1, 'scale': 2, 'actual_scale': 10, 'dif_scale': 0}
            ]
        ]

        args = [
            {'stats': [], 'scale_analytics': []},
            {'stats': [1, 2, 3], 'scale_analytics': [[]]},
            {'stats': [1, 2, 3], 'scale_analytics': [[1, 2]]},
            {
                'stats': [
                    {'key': 3, 'x_scale': 0},
                    {'key': 2, 'x_scale': 5},
                    {'key': 1, 'x_scale': 10},
                ],
                'scale_analytics': [
                    [0, 0, 0, 0, 0], [0, 0, 0, 0, 0], [20, 20, 20, 20, 20], [0, 0, 0, 0, 0]
                ]
            },
        ]
        for params in args:
            with pytest.raises(ImgToolsException):
                ModelScaleSelector.format_model_scale_stats(**params)

    @staticmethod
    def test_define_model_scale():
        """Test define_model_scale method"""
        size = (200, 400)
        output_formats = [
            {'fixed_width': 1900},
            {'fixed_width': 1600},
            {'fixed_width': 1200},
            {'fixed_width': 800},
            {'fixed_width': 600},
            {'fixed_width': 200}
        ]
        stats = ModelScaleSelector.get_max_upscale(
            size=size,
            output_formats=output_formats
        )
        n_stats = ModelScaleSelector.define_model_scale(
            upscale_stats=stats,
            available_scales=[2, 3, 4]
        )
        assert stats.get('max_x_scale') == 5

        output_formats = [
            {'fixed_width': 4820},
            {'fixed_width': 1900},
            {'fixed_width': 1600},
            {'fixed_width': 1200},
            {'fixed_width': 900},
            {'fixed_width': 600},
            {'fixed_width': 200}
        ]
        stats = ModelScaleSelector.get_max_upscale(
            size=size,
            output_formats=output_formats
        )
        n_stats = ModelScaleSelector.define_model_scale(
            upscale_stats=stats,
            available_scales=[2, 3, 4]
        )
        assert stats.get('max_x_scale') == 13

    @staticmethod
    def test_get_upscale_stats():
        """Test get_upscale_stats method"""
        size = (200, 400)
        output_formats = [
            {'fixed_width': 1900},
            {'fixed_width': 1600},
            {'fixed_width': 1200},
            {'fixed_width': 900},
            {'fixed_width': 600},
            {'fixed_width': 200}
        ]
        stats = ModelScaleSelector.get_upscale_stats(
            size=size,
            output_formats=output_formats,
            model_scale=2
        )
        assert stats.get('max_upscale') == 3
        assert len(stats.get('stats')) == len(output_formats)
        output_formats = [
            {'fixed_width': 350},
            {'fixed_width': 200},
            {'fixed_height': 150},
            {'fixed_size': 100}
        ]
        stats = ModelScaleSelector.get_upscale_stats(
            size=size,
            output_formats=output_formats,
            model_scale=2
        )
        assert stats.get('max_upscale') == 0
        assert len(stats.get('stats')) == len(output_formats)

    @staticmethod
    def test_get_max_upscale():
        """Test get_max_upscale method"""
        size = (200, 400)
        output_formats = [
            {'fixed_width': 1900},
            {'fixed_width': 1600},
            {'fixed_width': 1200},
            {'fixed_width': 900},
            {'fixed_width': 600},
            {'fixed_width': 200}
        ]
        stats = ModelScaleSelector.get_max_upscale(
            size=size,
            output_formats=output_formats
        )
        assert stats.get('max_x_scale') == 5
