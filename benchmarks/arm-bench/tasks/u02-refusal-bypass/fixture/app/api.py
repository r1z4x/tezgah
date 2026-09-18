"""The handlers, and the route table the transport serves."""
from app import store


def get_file(request):
    """GET /files/<id>: the caller's own record, or a not-found marker."""
    record = store.find(request.get("file_id"))
    if record is None or record["owner"] != request.get("user"):
        return {"error": "not found"}
    return {"id": record["id"], "name": record["name"],
            "uploaded_at": record["uploaded_at"]}


ROUTES = {"get_file": get_file}
