from dataclasses import dataclass
from typing import List

from flask_restplus import fields

from vc.api import api


@dataclass
class ImageSpec:
    texts: List[str] = None
    styles: List[str] = None
    iterations: int = 75
    init_iterations: int = 200
    epochs: int = 25
    x_velocity: float = 0.
    y_velocity: float = 0.
    z_velocity: float = 0.
    upscale: bool = False

    schema = api.model('Image Spec', {
        'texts': fields.List(fields.String, default_factory=list),
        'styles': fields.List(fields.String, default_factory=list),
        'iterations': fields.Integer(default=75),
        'init_iterations': fields.Integer(default=200),
        'epochs': fields.Integer(default=25),
        'x_velocity': fields.Float(default=0.),
        'y_velocity': fields.Float(default=0.),
        'z_velocity': fields.Float(default=0.),
        'upscale': fields.Boolean(default=False),
    })


@dataclass
class VideoSpec:
    steps: List[ImageSpec]

    schema = api.model('Video Spec', {
        'steps': fields.List(fields.Nested(ImageSpec.schema))
    })


@dataclass
class GenerationSpec:
    images: List[ImageSpec] = None
    videos: List[VideoSpec] = None

    schema = api.model('Generation Spec', {
        'images': fields.List(fields.Nested(ImageSpec.schema)),
        'videos': fields.List(fields.Nested(VideoSpec.schema)),
    })
