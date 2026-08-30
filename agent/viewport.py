"""Scale coordinates recorded at 1920x1080 to the controller viewport."""

REFERENCE_SIZE = (1920, 1080)


def image_size(image):
    try:
        height, width = image.shape[:2]
        return int(width), int(height)
    except Exception:
        return REFERENCE_SIZE


def scale_point(size, point):
    width, height = size
    return (
        round(point[0] * width / REFERENCE_SIZE[0]),
        round(point[1] * height / REFERENCE_SIZE[1]),
    )


def scale_roi(image, roi):
    width, height = image_size(image)
    x, y, roi_width, roi_height = roi
    return [
        round(x * width / REFERENCE_SIZE[0]),
        round(y * height / REFERENCE_SIZE[1]),
        max(1, round(roi_width * width / REFERENCE_SIZE[0])),
        max(1, round(roi_height * height / REFERENCE_SIZE[1])),
    ]


def scale_swipe(size, swipe):
    start = scale_point(size, swipe[:2])
    end = scale_point(size, swipe[2:4])
    return (*start, *end, swipe[4])
