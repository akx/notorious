import argparse
import dataclasses
import datetime
import gzip
import json
import os.path
import sqlite3
from typing import Iterable

DEFAULT_PATH = os.path.expanduser(
    "~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite"
)


@dataclasses.dataclass
class Entry:
    key: str
    timestamp: int
    folder: str
    title: str
    data: bytes

    @property
    def plaintext(self):
        d_data = gzip.decompress(self.data)
        if not d_data:
            return ""
        start_index = d_data.index(b"\x08\x00\x10\x00\x1a")
        start_index = d_data.index(b"\x12", start_index + 1) + 2
        end_index = d_data.index(
            b"\x04\x08\x00\x10\x00\x10\x00\x1a\x04\x08\x00", start_index
        )
        return d_data[start_index:end_index].decode("utf-8").strip()

    @property
    def date(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.timestamp)


def read_entries(conn) -> Iterable[Entry]:
    for key, folder, data, date, title in conn.execute(
        """
SELECT
  Z.Z_PK as key,
  _FOLDER.ZTITLE2 as folder,
  NOTEDATA.ZDATA as data,
  Z.ZCREATIONDATE1 as date,
  Z.ZTITLE1 as title
FROM
  ZICCLOUDSYNCINGOBJECT as Z
  INNER JOIN ZICCLOUDSYNCINGOBJECT AS _FOLDER ON Z.ZFOLDER = _FOLDER.Z_PK
  INNER JOIN ZICNOTEDATA as NOTEDATA ON Z.ZNOTEDATA = NOTEDATA.Z_PK
WHERE
  Z.Z_ENT IN (8, 9)
"""
    ):
        # Core Date dates are later than UNIX dates by 978307200 seconds
        timestamp = date + 978307200
        yield Entry(
            key=key,
            timestamp=timestamp,
            folder=folder,
            title=title,
            data=data,
        )


def output_entry(ent: Entry, format: str) -> None:
    if format == "jsonl":
        d = dataclasses.asdict(ent)
        d.pop("data")
        d.pop("timestamp")
        d.update(date=ent.date.isoformat(), text=ent.plaintext)
        print(json.dumps(d, ensure_ascii=False))
    elif format == "bodytext":
        print(ent.plaintext)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-i", "--input", dest="input", default=DEFAULT_PATH)
    ap.add_argument(
        "-o", "--output", dest="output", choices=("jsonl", "bodytext"), required=True
    )
    args = ap.parse_args()
    with sqlite3.connect(args.input) as conn:
        entries = list(read_entries(conn))
    format = args.output
    for ent in entries:
        output_entry(ent, format)


if __name__ == "__main__":
    main()
