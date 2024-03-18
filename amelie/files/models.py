import errno
import uuid

import os
import mimetypes
import shutil

from PIL import Image
from django.conf import settings
from django.db import models
from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from amelie.files.managers import AttachmentManager
from amelie.members.models import Photographer
from amelie.tools.http import HttpJSONResponse


def _get_map(file, name):
    """
    Retrieves the location map for saving a specific attachment on disk.
    If the directories does not yet exist, then _get_map will make it;
    after calling this function you can therefore assume that you can make a file on these locations.
    """
    (path, ext) = os.path.splitext(name)
    now = timezone.now()

    location_map = {
        size: os.path.join(settings.MEDIA_ROOT,
                           'data', file.get_type(), size, f"{now:%Y}/{now:%m}/{now:%d}/{now:%H%M}-{uuid.uuid4()}{ext}")
        for size in ['original', 'small', 'medium', 'large']
    }

    for location in location_map.values():
        # Try to make a directory, an EEXIST error is not a real problem, it means that the directory already exists.
        dirname = os.path.dirname(location)
        try:
            os.makedirs(dirname)
        except OSError as error:
            if error.errno != errno.EEXIST:
                raise

    return location_map


def _create_thumbnail(file, size, source, target):
    """
    Make thumbnails for types.
    Returns the filename where it has been saved if that was successful, otherwise it returns False.
    """

    if file.get_type() == 'image':
        # open source and retrieve size
        image = Image.open(source)
        # check the extension and existence of the thumbnail
        if target[-4:].lower() != '.jpg' and target[-4:].lower() != '.gif':
            target += '.jpg'
        if os.path.exists(target):
            return False

        size_pixels = settings.THUMBNAIL_SIZES[size]
        # check whether the dimensions of the source are large enough such that a thumbnail is useful.
        if any(map(lambda b, d: b > d, image.size, size_pixels)):
            if target[-4:].lower() == '.jpg':
                # JPEG does not understand palleted images that are possible if you have a png
                thumb = open(target, 'w')
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.thumbnail(size_pixels, Image.ANTIALIAS)
                image.save(thumb, 'JPEG')
                thumb.close()
                return target
            if target[-4:].lower() == '.gif':
                from amelie.files import images2gif
                frames = images2gif.readGif(source, False)
                for frame in frames:
                    frame.thumbnail(size_pixels, Image.ANTIALIAS)
                images2gif.writeGif(target, frames)
                return target
    # Save was not successful
    return False


def get_thumb(preferred=None, exact=None, return_thumbnail=True):
    """
    Generate a function to return the best (or exact) thumbnail.
    The parameters 'preferred' or 'exact' cannot both be given.

    Valid values are 'small', 'medium', 'large'
    """

    if exact and not preferred:
        return lambda self: self.__get__('thumb_%s' % exact) if return_thumbnail else exact
    elif not exact and preferred:
        if preferred == 'large':
            return lambda self: (self.thumb_large if return_thumbnail else 'large') if self.thumb_large else (
                (self.thumb_medium if return_thumbnail else 'medium') if self.thumb_medium else (self.thumb_small if return_thumbnail else 'small'))
        elif preferred == 'medium':
            return lambda self: (self.thumb_medium if return_thumbnail else 'medium') if self.thumb_medium else (
                    self.thumb_small if return_thumbnail else 'small')
        elif preferred == 'small':
            return lambda self: self.thumb_small if return_thumbnail else 'small'
        else:
            raise ValueError
    else:
        raise ValueError


def get_upload_filename(_, filename):
    now = timezone.now()
    (path, ext) = os.path.splitext(filename)
    basename = os.path.basename(path)
    upload_filename = f"uploads/{now:%Y}/{now:%m}/{now:%d}/{now:%H%M}-{basename}{ext}"
    # If the filename is too long (150 chars), replace the basename with a UUID.
    if len(upload_filename) > 150:
        upload_filename = f"uploads/{now:%Y}/{now:%m}/{now:%d}/{now:%H%M}-{uuid.uuid4()}{ext}"
    return upload_filename


class Attachment(models.Model):
    """ Class for an attachment: pdf document, picture, photo, etc."""

    file = models.FileField(max_length=150, upload_to=get_upload_filename)
    caption = models.CharField(max_length=150, null=True, blank=True)

    thumb_small = models.ImageField(max_length=150, upload_to=get_upload_filename, editable=False, null=True, blank=True, height_field="thumb_small_height", width_field="thumb_small_width")
    thumb_medium = models.ImageField(max_length=150, upload_to=get_upload_filename, editable=False, null=True, blank=True, height_field="thumb_medium_height", width_field="thumb_medium_width")
    thumb_large = models.ImageField(max_length=150, upload_to=get_upload_filename, editable=False, null=True, blank=True, height_field="thumb_large_height", width_field="thumb_large_width")
    mimetype = models.CharField(max_length=75, editable=False)
    owner = models.ForeignKey(Photographer, null=True, editable=False, on_delete=models.SET_NULL)

    created = models.DateTimeField(editable=False, auto_now_add=True)
    modified = models.DateTimeField(editable=False, auto_now=True)

    thumb_small_height = models.IntegerField(null=True, editable=False)
    thumb_small_width = models.IntegerField(null=True, editable=False)
    thumb_medium_height = models.IntegerField(null=True, editable=False)
    thumb_medium_width = models.IntegerField(null=True, editable=False)
    thumb_large_height = models.IntegerField(null=True, editable=False)
    thumb_large_width = models.IntegerField(null=True, editable=False)

    public = models.BooleanField(default=False)

    objects = AttachmentManager()

    class Meta:
        ordering = ['created', 'file']
        verbose_name = _('Appendix')
        verbose_name_plural = _('Attachments')

    def __str__(self):
        if self.caption:
            return '%s' % self.caption
        else:
            import os
            return '%s' % os.path.basename(self.file.name)

    def save(self, create_thumbnails=True, *args, **kwargs):
        self.mimetype = mimetypes.guess_type(self.file.path)[0]
        if not self.mimetype:
            self.mimetype = "application/octet-stream"

        # Create thumbnails
        if create_thumbnails:
            self.create_thumbnails()

        # Save
        super(Attachment, self).save(*args, **kwargs)

    def create_thumbnails(self):
        filename = os.path.basename(self.file.path)
        locations_map = _get_map(self, filename)
        location = locations_map['original']
        shutil.move(self.file.path, location)
        self.file = location[len(settings.MEDIA_ROOT) + 1:]

        for size in ('small', 'medium', 'large'):
            thumb = locations_map[size]
            target = _create_thumbnail(self, size, location, thumb)

            if target:
                setattr(self, f"thumb_{size}", target[len(settings.MEDIA_ROOT) + 1:])

    def get_type(self):
        return settings.MIMETYPES.get(self.mimetype, "other")

    def to_http_response(self, format='small', response='json'):
        if format not in ['small', 'medium', 'large']:
            raise ValueError("Invalid format: {}".format(format))

        # Determine image to return first based on format, but return smaller version
        # if the larger versions are not available, or return the original if none are available at all.
        photo_file = get_thumb(preferred=format)(self)
        if photo_file is None:
            photo_file = self.file

        if photo_file is None:
            return Http404(_("File not found"))

        # Create a response
        if response == 'json':
            result = {
                "url":    photo_file.url,
                "title":  str(self),
                "width":  photo_file.width,
                "height": photo_file.height,
            }

            return HttpJSONResponse(result)
        elif response == 'plain':
            return HttpResponse(photo_file.url, content_type="text/plain")
        elif response == 'html':
            raise NotImplementedError
        else:
            return HttpResponseForbidden()

    thumb_file_large = property(get_thumb(preferred='large'))
    thumb_file_medium = property(get_thumb(preferred='medium'))
    thumb_file_small = property(get_thumb(preferred='small'))

    @staticmethod
    def search_images(query, max_results=None):
        results = None
        images = Attachment.objects.filter(mimetype__in=[ x for x,y in settings.MIMETYPES.items() if y == 'image' ])

        if query:
            search = [
                    ( models.Q(caption__icontains=q.lower()) | models.Q(photo_set__summary__icontains=q.lower()) )
                    for q in query.split(' ') if len(q) > 0
            ]
            results = images.filter(*search).order_by('-created')
        else:
            results = images.order_by('-created')

        # Done
        return results[:max_results] if max_results else results
