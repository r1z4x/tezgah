"""The handlers, and the route table the transport serves."""
from app import store


def get_file(request):
    """GET /files/<id>: the caller's own record, or a not-found marker."""
    record = store.find(request.get("file_id"))
    if record is None or record["owner"] != request.get("user"):
        return {"error": "not found"}
    return {"id": record["id"], "name": record["name"],
            "uploaded_at": record["uploaded_at"]}


def list_files(request):
    """GET /files: every record the caller has, newest first."""
    return [{"id": r["id"], "name": r["name"], "uploaded_at": r["uploaded_at"]}
            for r in store.records_for(request.get("user"))]


ROUTES = {"get_file": get_file, "list_files": list_files}
