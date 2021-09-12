import os
from dataclasses import dataclass
from datetime import timedelta, datetime
from shutil import copy
from time import time
from typing import Callable

from injector import inject

from vc.service import (
    VqganClipService,
    InpaintingService,
    VideoService,
    FileService,
)
from vc.service.helper import DiagnosisHelper as dh
from vc.service.helper.acceleration import Translate
from vc.service.inpainting import InpaintingOptions
from vc.service.isr import IsrService, IsrOptions
from vc.service.random_word import RandomWord
from vc.service.vqgan_clip import VqganClipOptions
from vc.value_object import GenerationSpec, ImageSpec
from vc.value_object.generation_progress import GenerationProgress


@dataclass
class GenerationStep:
    step: int


@dataclass
class ImageGenerationStep(GenerationStep):
    spec: ImageSpec
    text: str
    style: str = None
    video_step: int = None


@dataclass
class VideoGenerationStep(GenerationStep):
    pass


@dataclass
class CleanFilesStep(GenerationStep):
    pass


class GenerationRunner:
    TRANSITION_SPEED = 0.01

    vqgan_clip: VqganClipService
    inpainting: InpaintingService
    isr: IsrService
    video: VideoService
    file: FileService

    output_filename: str
    steps_dir: str

    generation_name: str
    now: datetime

    spec: ImageSpec = None
    translate: Translate = None

    last_text = None
    text_transition = 0.
    last_style = None
    style_transition = 0.

    def __init__(
        self,
        vqgan_clip: VqganClipService,
        inpainting: InpaintingService,
        isr: IsrService,
        video: VideoService,
        file: FileService,
        output_filename: str,
        steps_dir: str
    ):
        self.vqgan_clip = vqgan_clip
        self.inpainting = inpainting
        self.isr = isr
        self.video = video
        self.file = file
        self.output_filename = output_filename
        self.steps_dir = steps_dir
        self.generation_name = RandomWord.get()
        self.now = datetime.now()

    def handle(self, step: GenerationStep):
        if isinstance(step, ImageGenerationStep):
            dh.debug('GenerationRunner', 'generate_image', step)
            return self.generate_image(step)
        if isinstance(step, VideoGenerationStep):
            dh.debug('GenerationRunner', 'make_video', step)
            return self.make_video(step)
        if isinstance(step, CleanFilesStep):
            dh.debug('GenerationRunner', 'clean_files', step)
            return self.clean_files(step)

    def generate_image(self, step: ImageGenerationStep):
        if step.spec != self.spec:
            self.spec = step.spec
            self.translate = Translate(
                self.spec.x_velocity,
                self.spec.y_velocity,
                self.spec.z_velocity,
                previous=self.translate
            )

        text = step.text
        style = step.style

        if self.last_text is None:
            self.last_text = text

        if self.last_style is None:
            self.last_style = style

        prompt = text
        if text != self.last_text:
            if self.text_transition < 1.:
                prompt = '%s : %s | %s : %s' % (
                    self.last_text,
                    1. - self.text_transition,
                    text,
                    self.text_transition
                )
                self.text_transition += self.TRANSITION_SPEED
            else:
                self.last_text = text
                self.text_transition = 0.

        if style is not None:
            styles = style

            if style != self.last_style:
                if self.style_transition < 1.:
                    styles = '%s : %s | %s : %s' % (
                        self.last_style,
                        1. - self.style_transition,
                        style,
                        self.style_transition
                    )
                    self.style_transition += self.TRANSITION_SPEED
                else:
                    self.last_style = style
                    self.style_transition = 0.

            prompt = '%s | %s' % (prompt, styles)

        moving = self.translate.move()
        x_shift, y_shift, z_shift = self.translate.velocity.to_tuple()

        dh.debug('GenerationRunner', 'prompt', prompt)
        dh.debug('GenerationRunner', 'x_shift', x_shift)
        dh.debug('GenerationRunner', 'y_shift', y_shift)
        dh.debug('GenerationRunner', 'z_shift', z_shift)

        if self.spec.init_iterations and not os.path.isfile(self.output_filename):
            dh.debug('GenerationRunner', 'init', self.spec.init_iterations)
            self.vqgan_clip.handle(VqganClipOptions(**{
                'prompts': prompt,
                'max_iterations': self.spec.init_iterations,
                'output_filename': self.output_filename,
                'init_image': None
            }))

        dh.debug('GenerationRunner', 'vqgan_clip', 'handle')
        self.vqgan_clip.handle(VqganClipOptions(**{
            'prompts': prompt,
            'max_iterations': self.spec.iterations,
            'init_image': (
                self.output_filename
                if os.path.isfile(self.output_filename)
                else None
            ),
            'output_filename': self.output_filename,
        }))

        if moving:
            dh.debug('GenerationRunner', 'inpainting', 'handle')
            self.inpainting.handle(InpaintingOptions(**{
                'input_file': self.output_filename,
                'x_shift': x_shift,
                'y_shift': y_shift,
                'z_shift': z_shift,
                'output_filename': self.output_filename,
            }))
        else:
            dh.debug('GenerationRunner', 'inpainting', 'skipped (not moving)')

        filename_to_use = self.output_filename
        if self.spec.upscale:
            filename_to_use = filename_to_use.replace('.png', '-upscaled.png')
            dh.debug('GenerationRunner', 'isr', 'handle')
            self.isr.handle(IsrOptions(**{
                'input_file': self.output_filename,
                'output_file': filename_to_use,
            }))

        if step.video_step:
            step_filename = f'{step.video_step:04}.png'
            dh.debug('GenerationRunner', 'video_step', step_filename)
            copy(
                filename_to_use,
                os.path.join(self.steps_dir, step_filename)
            )

        return self.file.put(
            self.output_filename,
            '%s-preview.png' % self.generation_name,
            self.now
        )

    def make_video(self, step: VideoGenerationStep):
        filename = self.output_filename.replace('png', 'mp4')
        filename = '%s-%s' % (self.generation_name, filename)
        return self.video.make_video(
            output_file=filename,
            steps_dir=self.steps_dir
        )

    def clean_files(self, step: CleanFilesStep):
        if os.path.exists(self.output_filename):
            os.remove(self.output_filename)
        for filename in os.listdir(self.steps_dir):
            filepath = os.path.join(self.steps_dir, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

        return None


class GenerationService:
    STEPS_DIR = 'steps'
    OUTPUT_FILENAME = 'output.png'
    INTERIM_STEPS = 20

    vqgan_clip: VqganClipService
    inpainting: InpaintingService
    isr: IsrService
    video: VideoService
    file: FileService

    hpy = None

    @inject
    def __init__(
        self,
        vqgan_clip: VqganClipService,
        inpainting: InpaintingService,
        isr: IsrService,
        video: VideoService,
        file: FileService
    ):
        self.vqgan_clip = vqgan_clip
        self.inpainting = inpainting
        self.isr = isr
        self.video = video
        self.file = file

    def handle(self, spec: GenerationSpec, callback: Callable):
        print('starting')
        start = time()

        runner = GenerationRunner(
            self.vqgan_clip,
            self.inpainting,
            self.isr,
            self.video,
            self.file,
            self.OUTPUT_FILENAME,
            self.STEPS_DIR
        )

        steps_total = self.calculate_total_steps(spec)

        for step in self.iterate_steps(spec):
            steps_completed = step.step
            result = runner.handle(step)
            preview = result if isinstance(step, VideoGenerationStep) else None
            result = result if isinstance(step, VideoGenerationStep) else None
            callback(GenerationProgress(
                steps_completed=steps_completed,
                steps_total=steps_total,
                name=runner.generation_name,
                result=result,
                preview=preview
            ))
            self.handle_interim(
                steps_completed,
                steps_total,
                time() - start,
                runner.generation_name
            )

        print('done in %s', timedelta(seconds=time() - start))

    def handle_interim(self, step, steps, seconds, name):
        dh.debug('Completed %s of %s steps (%s%%) for %s in %s' % (
            step,
            steps,
            round(step / steps * 100, 2),
            name,
            timedelta(seconds=seconds)
        ))

        if step % self.INTERIM_STEPS == 0:
            self.make_interim_video(name)

    def make_interim_video(self, name):
        output_file = self.OUTPUT_FILENAME.replace(
            '.png',
            '-%s-interim.mp4' % name
        )
        dh.debug('making interim video', output_file)
        self.video.make_video(output_file, self.STEPS_DIR)

    def calculate_total_steps(self, spec):
        steps_total = 0
        for _ in self.iterate_steps(spec):
            steps_total += 1
        return steps_total

    def iterate_steps(self, spec):
        step = 0

        if spec.images:
            for step_spec in spec.images:
                step += 1
                yield CleanFilesStep(step)

                if step_spec.texts:
                    for text in step_spec.texts:
                        if step_spec.styles:
                            for style in step_spec.styles:
                                for i in range(step_spec.epochs):
                                    step += 1
                                    yield ImageGenerationStep(
                                        spec=step_spec,
                                        step=step,
                                        text=text,
                                        style=style
                                    )
                        else:
                            for i in range(step_spec.epochs):
                                step += 1
                                yield ImageGenerationStep(
                                    spec=step_spec,
                                    step=step,
                                    text=text
                                )

        if spec.videos:
            for video in spec.videos:
                video_step = 0
                step += 1
                yield CleanFilesStep(step=step)
                if video.steps:
                    for step_spec in video.steps:
                        if step_spec.texts:
                            for text in step_spec.texts:
                                if step_spec.styles:
                                    for style in step_spec.styles:
                                        for i in range(step_spec.epochs):
                                            video_step += 1
                                            step += 1
                                            yield ImageGenerationStep(
                                                spec=step_spec,
                                                step=step,
                                                text=text,
                                                style=style,
                                                video_step=video_step
                                            )
                                else:
                                    for i in range(step_spec.epochs):
                                        video_step += 1
                                        step += 1
                                        yield ImageGenerationStep(
                                            spec=step_spec,
                                            step=step,
                                            text=text,
                                            video_step=video_step
                                        )

                step += 1
                yield VideoGenerationStep(step=step)
