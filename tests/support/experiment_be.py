"""A be public API for several projects at once (mock transport) and a Langfuse API that matches it, for the
experiment runner tests. A project answers `polls_needed - 1` GETs as running, then as finished."""

import copy
import json
from collections.abc import Callable

import httpx

TOKEN = "tok-experiment-secret"
PASSWORD = "experiment-password-1234"
LF_KEYS = {"LANGFUSE_PUBLIC_KEY": "pk-lf-EXPPUBLIC", "LANGFUSE_SECRET_KEY": "sk-lf-EXPSECRET", "LANGFUSE_HOST": "http://lf.test"}
PER_TRACE_TOKENS = (100, 20)  # input, output of the single llm_call of every trace


class MultiBe:
    def __init__(
        self,
        base_project: dict,
        *,
        polls_needed: int = 2,
        outcome_of: Callable[[str], str] | None = None,
        mutate: Callable[[dict], dict] | None = None,
        create_status: int = 201,
    ) -> None:
        self.base = base_project
        self.polls_needed = polls_needed
        self.outcome_of = outcome_of or (lambda idea: "completed")  # completed | failed | stuck
        self.mutate = mutate
        self.create_status = create_status
        self.requests: list[httpx.Request] = []
        self.created: list[dict] = []
        self.projects: dict[str, dict] = {}
        self.polls: dict[str, int] = {}
        self.active: set[str] = set()
        self.max_active = 0

    # -- be
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/users/":
            return httpx.Response(201, json={})
        if request.method == "POST" and path == "/api/auth/login":
            return httpx.Response(200, json={"access_token": TOKEN, "refresh_token": "r"})
        if request.method == "POST" and path == "/api/generation":
            body = json.loads(request.content)
            if self.create_status != 201:
                return httpx.Response(self.create_status, text="refused")
            project_id = f"p-{len(self.created) + 1}"
            self.created.append(body)
            self.projects[project_id] = self._project(project_id, body["idea"])
            self.polls[project_id] = 0
            self.active.add(project_id)
            self.max_active = max(self.max_active, len(self.active))
            return httpx.Response(201, json={"id": project_id, "status": "running", "rows": []})
        if request.method == "GET" and path.startswith("/api/projects/"):
            project_id = path.rsplit("/", 1)[1]
            self.polls[project_id] += 1
            project = self.projects[project_id]
            outcome = self.outcome_of(project["idea"])
            if outcome == "stuck" or self.polls[project_id] < self.polls_needed:
                return httpx.Response(200, json={**project, "status": "running", "rows": project["rows"][:2]})
            self.active.discard(project_id)
            return httpx.Response(200, json=project)
        return httpx.Response(404)

    def _project(self, project_id: str, idea: str) -> dict:
        project = copy.deepcopy(self.base)
        project.update(id=project_id, idea=idea)
        outcome = self.outcome_of(idea)
        if outcome == "failed":
            project["status"] = "failed"
            row = project["rows"][3]
            row["status"] = "error"
            row["error"] = {"code": "generation_failed", "message": "the model refused"}
        return self.mutate(project) if self.mutate else project

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    # -- Langfuse
    def langfuse_handler(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        if request.url.path == "/api/public/traces":
            project = self.projects.get(params["sessionId"])
            traces = [] if project is None else [
                {"id": f"{project['id']}:{r['id']}", "metadata": {"block": r["stage"], "row_id": r["id"]}, "tags": [r["stage"]]}
                for r in project["rows"]
            ]
            return httpx.Response(200, json={"data": traces, "meta": {"page": 1, "limit": 100, "totalItems": len(traces), "totalPages": 1}})
        usage = {"input": PER_TRACE_TOKENS[0], "output": PER_TRACE_TOKENS[1], "total": sum(PER_TRACE_TOKENS)}
        return httpx.Response(200, json={"data": [{"name": "llm_call", "usageDetails": usage}], "meta": {"page": 1, "limit": 100, "totalItems": 1, "totalPages": 1}})

    def langfuse_transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.langfuse_handler)

    @property
    def tokens_per_project(self) -> int:
        return len(self.base["rows"]) * sum(PER_TRACE_TOKENS)
