from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
from os import path, PathLike
from typing import Self

import requests
import base64
import io

## Filters ##

class Filter:
    def apply(self, image: Image.Image, draw: ImageDraw.Draw):
        return image
    
    def before_render(
        self,
        image: Image.Image,
        draw: ImageDraw.Draw,
        pos: tuple,
        size: tuple,
        mask: Image.Image=None
    ):
        return image

class Blur(Filter):
    def __init__(self, radius: int=5):
        self.radius = radius

    def apply(self, image: Image.Image, draw: ImageDraw.Draw):
        return image.filter(ImageFilter.GaussianBlur(radius=self.radius))

class BlurBehind(Filter):
    def __init__(self, radius: int=5):
        self.radius = radius
    
    def before_render(
        self,
        image: Image.Image,
        draw: ImageDraw.Draw,
        pos: tuple,
        size: tuple,
        mask: Image.Image=None
    ):
        mask = mask.convert("RGBA")
        for x in range(mask.width):
            for y in range(mask.height):
                if mask.getpixel((x, y)) != (0, 0, 0, 0):
                    mask.putpixel((x, y), (255, 255, 255, 255))

        crop = image.crop((pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]))
        crop = crop.filter(ImageFilter.GaussianBlur(radius=self.radius))
        image.paste(crop, (pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]), mask)
        return image

class Grayscale(Filter):
    def apply(self, image: Image.Image, draw: ImageDraw.Draw):
        return ImageOps.grayscale(image)

class GrayscaleBehind(Filter):
    def before_render(
        self,
        image: Image.Image,
        draw: ImageDraw.Draw,
        pos: tuple,
        size: tuple,
        mask: Image.Image=None
    ):
        mask = mask.convert("RGBA")
        for x in range(mask.width):
            for y in range(mask.height):
                if mask.getpixel((x, y)) != (0, 0, 0, 0):
                    mask.putpixel((x, y), (255, 255, 255, 255))

        crop = image.crop((pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]))
        crop = ImageOps.grayscale(crop)
        image.paste(crop, (pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]), mask)
        return image

class Invert(Filter):
    def apply(self, image: Image.Image, draw: ImageDraw.Draw):
        return ImageOps.invert(image)

class InvertBehind(Filter):
    def before_render(
        self,
        image: Image.Image,
        draw: ImageDraw.Draw,
        pos: tuple,
        size: tuple,
        mask: Image.Image=None
    ):
        mask = mask.convert("RGBA")
        for x in range(mask.width):
            for y in range(mask.height):
                if mask.getpixel((x, y)) != (0, 0, 0, 0):
                    mask.putpixel((x, y), (255, 255, 255, 255))

        crop = image.crop((pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]))
        crop = ImageOps.invert(crop)
        image.paste(crop, (pos[0], pos[1], pos[0] + size[0], pos[1] + size[1]), mask)
        return image

## Core Classes ##

class FontSet:
    def __init__(
        self,
        base: PathLike,
        bold: PathLike=None,
        italic: PathLike=None,
        bold_italic: PathLike=None
    ):
        self.base = ImageFont.truetype(base)
        self.bold = ImageFont.truetype(bold) if bold else None
        self.italic = ImageFont.truetype(italic) if italic else None
        self.bold_italic = ImageFont.truetype(bold_italic) if bold_italic else None
    
    def get(self, size: int=14, bold: bool=False, italic: bool=False):
        font = self.base
        if bold:
            font = self.bold
        if italic:
            font = self.italic
        if bold and italic:
            font = self.bold_italic
        return font.font_variant(size=size)
    
    @classmethod
    def default(cls):
        return cls(
            path.join(path.dirname(__file__), "..", "fonts", "LiberationSans-Regular.ttf"),
            path.join(path.dirname(__file__), "..", "fonts", "LiberationSans-Bold.ttf"),
            path.join(path.dirname(__file__), "..", "fonts", "LiberationSans-Italic.ttf"),
            path.join(path.dirname(__file__), "..", "fonts", "LiberationSans-BoldItalic.ttf")
        )

class Canvas:
    def __init__(
        self,
        width: int=512,
        height: int=512,
        font_set: FontSet=None,
        image: Image.Image=None,
        background: str="#FFFFFF"
    ):
        if width and image:
            raise ValueError("Width provided but an image has already been set!")
        if height and image:
            raise ValueError("Height provided but an image has already been set!")
        if image is None:
            image = Image.new("RGBA", (width or 512, height or 512), background)
        
        self.image = image
        self.width = image.width
        self.height = image.height
        self.draw = ImageDraw.Draw(image)
        self.font_set = font_set or FontSet.default()

    @classmethod
    def from_url(cls, url: str, *args, **kwargs) -> Self:
        response = requests.get(url)
        if response.ok:
            return cls(Image.open(io.BytesIO(response.content)), *args, **kwargs)
        raise ValueError(f"Failed to download image with status <{response.status_code}> and response: {response.text}")
    
    @classmethod
    def from_path(cls, path: PathLike, *args, **kwargs) -> Self:
        return cls(Image.open(path), *args, **kwargs)

    ## Save Functions ##

    def save(self, filename: str) -> None:
        self.image.save(filename)
    
    def save_b64(self) -> bytes:
        buffer = io.BytesIO()
        self.image.save(buffer, "PNG")
        buffer.seek(0)
        return base64.b64encode(buffer.read())
    
    ## Render Functions ##
    
    def rounded_rectangle(
        self,
        pos: tuple,
        size: tuple,
        anchor_point: tuple=(0, 0),
        radius: int=10,
        outline: str="#000000",
        width: int=0,
        corners: tuple=None,
        alpha: int=255,
        
        image: str=None,
        fill: str=None,
        
        crop: tuple=None,
        filters: list=[]
    ) -> Self:
        if image and fill:
            raise ValueError("Both image and fill cannot be set at the same time.")
        if fill is None:
            fill = "#FFFFFF"
        if image:
            mask = Image.new("L", size, 0)
            mask_draw = ImageDraw.Draw(mask)
            if alpha < 255:
                mask_draw.rounded_rectangle([(0, 0), size], radius, fill=(255, 255, 255, alpha), corners=corners)
            else:
                mask_draw.rounded_rectangle([(0, 0), size], radius, fill="white", corners=corners)
            
            download = requests.get(image)
            if download.ok:
                im = Image.open(io.BytesIO(download.content))
                im = ImageOps.fit(im, size, Image.Resampling.LANCZOS)
                new_pos = self.get_position(pos, size, anchor_point)
                if width > 0:
                    self.draw.rounded_rectangle(
                        [
                            (new_pos[0] - width, new_pos[1] - width),
                            (new_pos[0] + size[0] + width, new_pos[1] + size[1] + width)
                        ],
                        radius,
                        fill=outline,
                        corners=corners
                    )
                if crop:
                    im = im.crop(crop)
                for filter in filters:
                    if getattr(filter, "before_render", None):
                        self.image = filter.before_render(self.image, self.draw, new_pos, size, mask)
                    if getattr(filter, "apply", None):
                        im = filter.apply(im, self.draw)
                if alpha < 255:
                    self.image.alpha_composite(im, new_pos)
                else:
                    self.image.paste(im, (new_pos[0], new_pos[1], new_pos[0] + im.size[0], new_pos[1] + im.size[1]), mask)
                return self
            else:
                raise ValueError(f"Image download failed with status <{download.status_code}> and response: {download.text}")
        else:
            new_pos = self.get_position(pos, size, anchor_point)
            im = Image.new("RGBA", size, (0, 0, 0, 0))
            im_draw = ImageDraw.Draw(im)
            fill = self.to_rgba(fill, alpha)
            im_draw.rounded_rectangle(
                [(0, 0), size],
                radius,
                fill=fill,
                outline=outline,
                width=width,
                corners=corners
            )
            if crop:
                im = im.crop(crop)
            for filter in filters:
                if getattr(filter, "before_render", None):
                    self.image = filter.before_render(self.image, self.draw, new_pos, size, im)
                if getattr(filter, "apply", None):
                    im = filter.apply(im, self.draw)
            if alpha < 255:
                self.image.alpha_composite(im, new_pos)
            else:
                self.image.paste(im, (new_pos[0], new_pos[1], new_pos[0] + im.size[0], new_pos[1] + im.size[1]), im)
            return self
    
    def ellipse(
        self,
        pos: tuple,
        size: tuple,
        anchor_point: tuple=(0, 0),
        outline: str="#000000",
        width: int=0,
        alpha: int=255,
        
        fill: str=None,
        image: str=None,
        
        crop: tuple=None,
        filters: list=[]
    ) -> Self:
        if image and fill:
            raise ValueError("Both image and fill cannot be set at the same time.")
        if fill is None:
            fill = "#FFFFFF"
        if image:
            mask = Image.new("L", size, 0)
            mask_draw = ImageDraw.Draw(mask)
            if alpha < 255:
                mask_draw.ellipse([(0, 0), size], fill=(255, 255, 255, alpha))
            else:
                mask_draw.ellipse([(0, 0), size], fill="white")

            download = requests.get(image)
            if download.ok:
                im = Image.open(io.BytesIO(download.content))
                im = ImageOps.fit(im, size, Image.Resampling.LANCZOS)
                new_pos = self.get_position(pos, size, anchor_point)
                if width > 0:
                    self.draw.ellipse(
                        [
                            (new_pos[0] - width, new_pos[1] - width),
                            (new_pos[0] + size[0] + width, new_pos[1] + size[1] + width)
                        ],
                        fill=outline,
                    )
                if crop:
                    im = im.crop(crop)
                for filter in filters:
                    if getattr(filter, "before_render", None):
                        self.image = filter.before_render(self.image, self.draw, new_pos, size, mask)
                    if getattr(filter, "apply", None):
                        im = filter.apply(im, self.draw)
                if alpha < 255:
                    self.image.alpha_composite(im, new_pos)
                else:
                    self.image.paste(im, (new_pos[0], new_pos[1], new_pos[0] + im.size[0], new_pos[1] + im.size[1]), mask)
                return self
            else:
                raise ValueError(f"Image download failed with status <{download.status_code}> and response: {download.text}")
        else:
            new_pos = self.get_position(pos, size, anchor_point)
            im = Image.new("RGBA", size, (0, 0, 0, 0))
            im_draw = ImageDraw.Draw(im)
            fill = self.to_rgba(fill, alpha)
            im_draw.ellipse(
                [(0, 0), size],
                fill=fill,
                outline=outline,
                width=width
            )
            if crop:
                im = im.crop(crop)
            for filter in filters:
                if getattr(filter, "before_render", None):
                    self.image = filter.before_render(self.image, self.draw, new_pos, size, im)
                if getattr(filter, "apply", None):
                    im = filter.apply(im, self.draw)
            if alpha < 255:
                self.image.alpha_composite(im, new_pos)
            else:
                self.image.paste(im, (new_pos[0], new_pos[1], new_pos[0] + im.size[0], new_pos[1] + im.size[1]), mask)
            return self
    
    def text_bounds(
        self,
        pos: tuple,
        text: str,
        size: int=16,
        font_set: FontSet=None,
        anchor: str="la",
        
        bold: bool=False,
        italic: bool=False,
    ) -> tuple:
        if font_set is None:
            font_set = self.font_set

        font = font_set.get(
            bold=bold,
            italic=italic,
            size=size
        )
        return self.draw.textbbox(
            pos,
            text,
            font=font,
            anchor=anchor
        )
    
    def text(
        self,
        pos: tuple,
        text: str,
        size: int=16,
        font_set: FontSet=None,
        anchor: str="la",
        fill: str="#000000",
        alpha: int=255,
        
        bold: bool=False,
        italic: bool=False,
        underline: bool=False,
        strikethrough: bool=False,

        filters: list=[]
    ) -> Self:
        if font_set is None:
            font_set = self.font_set
        
        im = Image.new("RGBA", self.image.size, 0)
        draw = ImageDraw.Draw(im)
        font = font_set.get(
            bold=bold,
            italic=italic,
            size=size
        )
        
        draw.text(
            pos,
            text,
            font=font,
            fill=self.to_rgba(fill, alpha),
            anchor=anchor
        )
        bounds = self.text_bounds(
            pos,
            text,
            size=size,
            font_set=font_set,
            anchor=anchor
        )
        if underline:
            draw.line(
                [
                    (bounds[0], bounds[1] + size),
                    (bounds[2], bounds[1] + size)
                ],
                fill=self.to_rgba(fill, alpha)
            )
        if strikethrough:
            draw.line(
                [
                    (bounds[0], bounds[1] + size // 2),
                    (bounds[2], bounds[1] + size // 2)
                ],
                fill=self.to_rgba(fill, alpha)
            )
        
        for filter in filters:
            if getattr(filter, "before_render", None):
                filter.before_render(im, self.draw, pos, size, None)
            if getattr(filter, "apply", None):
                im = filter.apply(im, self.draw)
        
        self.image.paste(im, (0, 0), im)
        return self
    
    ## Helper Utilities ##
    
    def bound_width(self, bounds: tuple) -> int:
        return abs(bounds[2] - bounds[0])
    
    def bound_height(self, bounds: tuple) -> int:
        return abs(bounds[3] - bounds[1])
    
    def to_rgba(self, color: str, alpha: int=255) -> tuple:
        if type(color) is str:
            # Assume color is a hex code and translate it to RGB
            color = int(color.replace("#", ""), 16)
            color = (
                (color >> 16) & 0xFF,
                (color >> 8) & 0xFF,
                color & 0xFF
            )
        return (color[0], color[1], color[2], alpha)
    
    def get_position(
        self,
        pos: tuple,
        size: tuple,
        anchor_point: tuple=(0, 0)
    ) -> tuple:
        return (
            int(pos[0] + anchor_point[0] * size[0]),
            int(pos[1] + anchor_point[1] * size[1])
        )
    
    def get_dominant_color(self, image: Image.Image) -> tuple:
        if type(image) is str:
            download = requests.get(image)
            if download.ok:
                image = Image.open(io.BytesIO(download.content))
            else:
                raise ValueError(f"Image download failed with status <{download.status_code}> and response: {download.text}")
        image: Image.Image = image.convert("RGB")
        image.thumbnail((100, 100))
        pixels = image.getdata()
        r, g, b = 0, 0, 0
        for pixel in pixels:
            r += pixel[0]
            g += pixel[1]
            b += pixel[2]
        total = len(pixels)
        return (r // total, g // total, b // total)