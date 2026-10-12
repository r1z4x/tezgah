"""CSV export of profiles. The mailing tool parses this text: its layout is fixed."""
import csv
import io

HEADER = ["name", "email", "tags"]


def to_csv(profiles):
    """CSV text: the header row, then one row per profile, tags joined by ';'."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(HEADER)
    for p in profiles:
        writer.writerow([p["name"], p["mail"], p["tags"].replace(",", ";")])
    return out.getvalue()
