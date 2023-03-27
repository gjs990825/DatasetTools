r"""This script takes multiple label_directory-video_path pairs, makes yolo-styled dataset out of them.
Primarily for solving CVAT exporting problem(too slow for large datasets),
export labels and video respectively, use this tool to extract and arrange the frames and labels.

NOTE:
    FFmpeg is required for frame extraction.

EXAMPLE:
    python make_dataset_from_labels_and_video.py -i path_to_labels_1 path_to_video_1
    -i path_to_labels_2 path_to_video_2
    -o path_to_output
    -image_ext .png
    -ffmpeg_exec path_to_ffmpeg
"""

import argparse
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from multiprocessing import Pool
from pathlib import Path

LABEL_PATTERN = re.compile(r".*?\D?(\d+)")


@dataclass(frozen=True)
class Label:
    path: Path  # path to this label file
    id: int  # label frame position(starting form 0)


def extract_frames(video: Path, output_dir: Path, output_pattern, ffmpeg_exec=None) -> bool:
    """extract all frames to output_dir using ffmpeg tool"""
    if not ffmpeg_exec:
        ffmpeg_exec = 'ffmpeg'
    output = output_dir.joinpath(output_pattern)
    return subprocess.run(f'{ffmpeg_exec} -i {video.absolute()} {output}').returncode == 0


def extract_label_id(name) -> int:
    """find id number in file name"""
    numbers = LABEL_PATTERN.findall(name)
    if numbers:
        return int(numbers[0])
    raise Exception(f'no id found in: {name}')


def get_valid_labels(label_dir: Path, label_ext: str, ignore_empty=True) -> list[Label]:
    """find labels in label_dir with extension name"""
    label_ext = label_ext.lower()
    valid_labels = []
    for item in label_dir.iterdir():
        if item.suffix.lower() != label_ext:
            continue
        if ignore_empty and item.stat().st_size == 0:
            continue
        valid_labels.append(Label(item, extract_label_id(item.stem)))
    return valid_labels


def make_dataset(label_path: Path, label_ext, video_path: Path, clip_number, output_dir, image_ext,
                 ffmpeg_exec) -> bool:
    # find labels
    labels = get_valid_labels(label_path, label_ext)
    if not labels:
        print('no labels here, check path and extension')
        return False

    # make workplace
    temp_dir = output_dir.joinpath(str(uuid.uuid4()))
    temp_dir.mkdir(exist_ok=True)

    result = extract_frames(video_path, temp_dir, f'C{clip_number:02d}_%06d{image_ext}', ffmpeg_exec)
    if not result:
        print('frame extraction failed')
        return False

    # copy label and it's correspondent image to output, rename label to match image name
    for label in labels:
        # move out of temp directory(ffmpeg output starts at 1)
        file_name = f'C{clip_number:02d}_{label.id + 1:06d}{image_ext}'
        image_path = temp_dir.joinpath(file_name).replace(output_dir.joinpath(file_name))
        # copy and rename label, move image
        label_copy_to = image_path.with_suffix(label.path.suffix)
        shutil.copy(label.path, label_copy_to)

    # clean mess
    shutil.rmtree(temp_dir)
    return True


def run(args):
    output_dir = Path(args.o)
    output_dir.mkdir(exist_ok=True)
    label_ext = args.label_ext
    image_ext = args.image_ext
    ffmpeg_exec = args.ffmpeg_exec

    works = []
    for clip_number, (label_path, video_path) in enumerate(args.i):
        label_path, video_path = Path(label_path), Path(video_path)
        works.append((label_path,
                      label_ext,
                      video_path,
                      clip_number,
                      output_dir,
                      image_ext,
                      ffmpeg_exec,))

    # multiprocessing go🚀
    with Pool() as p:
        result = p.starmap(make_dataset, works)
        print('SUCCESS!' if all(result) else 'OOPS!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', action='append', nargs=2, metavar=('label_dir', 'video_path'), required=True,
                        help='label directory and video path, multiple input pairs supported')
    parser.add_argument('-o', type=str, required=True, help='output directory')
    parser.add_argument('-label_ext', type=str, default='.txt', help='label file extension name(with dot)')
    parser.add_argument('-image_ext', type=str, default='.bmp', help='image file extension name(with dot)')
    parser.add_argument('-ffmpeg_exec', type=str, help='specify a ffmpeg executable')
    args = parser.parse_args()

    run(args)
