#!/usr/bin/python3 -BP
# -*- coding: utf-8 -*-
# select_recordings Copyright (C) 2026  Stuart Pook (http://www.pook.it/)
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Selects filenames of the form VID_yyyyMMdd_hhmmss.ext (e.g. VID_20260910_203733.mp4)
# whose embedded date falls within [start_date, end_date], whose embedded time falls
# within [start_time, end_time], and whose weekday matches start_date's weekday.

import sys
import re
import argparse
import logging as do_not_use
import pathlib
from datetime import date, datetime, time

logger = do_not_use.getLogger(__name__)

FILENAME_RE = re.compile(r"VID_(\d{8})_(\d{6})\.\w+")


def set_logging_level(loglevel: int) -> None:
    script_name = pathlib.Path(sys.argv[0]).name
    do_not_use.basicConfig(
        level=do_not_use.WARNING,
        format=f"{script_name}:%(levelname)s:%(name)s:%(message)s",
        force=True,
    )
    logger.setLevel(loglevel)


def error(message: str) -> None:
    logger.critical(message)
    sys.exit(8)


def parse_date(text: str) -> date:
    try:
        return datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        error(f"invalid date (expected dd/MM/yyyy): {text}")
        raise  # unreachable, error() exits; keeps type checkers happy


def parse_time(text: str) -> time:
    try:
        return datetime.strptime(text, "%H:%M").time()
    except ValueError:
        error(f"invalid time (expected HH:MM): {text}")
        raise


def default_end_date(start_date: date) -> date:
    """The next 26 June strictly after start_date."""
    candidate = date(start_date.year, 6, 26)
    if candidate <= start_date:
        candidate = date(start_date.year + 1, 6, 26)
    return candidate


def parse_filename(name: str) -> tuple[date, time] | None:
    match = FILENAME_RE.fullmatch(pathlib.Path(name).name)
    if not match:
        return None
    date_part, time_part = match.groups()
    try:
        file_date = datetime.strptime(date_part, "%Y%m%d").date()
        file_time = datetime.strptime(time_part, "%H%M%S").time()
    except ValueError as e:
        logger.warning("could not parse embedded date/time in %r: %s", name, e)
        return None
    return file_date, file_time


def matches(
    name: str,
    start_date: date,
    end_date: date,
    start_time: time,
    end_time: time,
) -> bool:
    parsed = parse_filename(name)
    if parsed is None:
        logger.info("skipping, no embedded date/time found: %s", name)
        return False
    file_date, file_time = parsed
    if not (start_date <= file_date <= end_date):
        return False
    if not (start_time <= file_time <= end_time):
        return False
    if file_date.weekday() != start_date.weekday():
        return False
    return True


def read_filenames_from_stdin() -> list[str]:
    return [line.rstrip("\n") for line in sys.stdin if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="select filenames of the form VID_yyyyMMdd_hhmmss.ext whose embedded "
                    "date/time falls within given date and time ranges, and whose weekday "
                    "matches start_date's weekday",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.set_defaults(loglevel='warning')
    parser.add_argument("--start_date", "--date", help="start date, dd/MM/yyyy")
    parser.add_argument(
        "--end-date", metavar="DATE",
        help="end date, dd/MM/yyyy, must be after start_date (default: next 26 June after start_date)")
    parser.add_argument("--start-time", metavar="TIME", default="20:00", help="start time, HH:MM")
    parser.add_argument("--end-time", metavar="TIME", default="22:15", help="end time, HH:MM")
    parser.add_argument("files", nargs="*", help="filenames to filter (default: read from stdin)")
    parser.add_argument(
        "-v", "--verbose", "--debug", dest='loglevel', action="store_const", const='debug', help="debug loglevel")
    parser.add_argument("-l", "--loglevel", metavar="LEVEL", help="set logging level")

    options = parser.parse_args()

    set_logging_level(getattr(do_not_use, options.loglevel.upper(), None))

    start_date = parse_date(options.start_date)
    end_date = parse_date(options.end_date) if options.end_date else default_end_date(start_date)
    if end_date <= start_date:
        error(f"end_date ({end_date}) must be after start_date ({start_date})")

    start_time = parse_time(options.start_time)
    end_time = parse_time(options.end_time)
    if end_time <= start_time:
        error(f"end_time ({end_time}) must be after start_time ({start_time})")

    logger.info(
        "date range %s to %s, time range %s to %s, weekday %s",
        start_date, end_date, start_time, end_time, start_date.strftime("%A"))

    filenames = options.files if options.files else read_filenames_from_stdin()

    for name in filenames:
        if matches(name, start_date, end_date, start_time, end_time):
            print(name)


if __name__ == "__main__":
    main()
