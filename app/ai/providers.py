from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib import error, request

from pydantic import SecretStr

from app.core.config import Settings

CompletionClient = Callable[[list[dict[str, str]]], Mapping[str, object]]

DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "task_agent.md"

FIELD_ALIASES = {
    "taskName": "task_name",
    "taskDescription": "task_description",
    "taskGoal": "task_goal",
    "taskSource": "task_source",
    "mainAssigneeEmployeeNo": "main_assignee_employee_no",
    "reportToEmployeeNo": "report_to_employee_no",
    "reportToLevel": "report_to_level",
    "reviewerEmployeeNo": "reviewer_employee_no",
    "departmentId": "department_id",
    "startTime": "start_time",
    "deadline": "deadline",
    "estimatedHours": "estimated_hours",
    "taskWeight": "task_weight",
    "deliverable": "deliverable",
    "acceptanceCriteria": "acceptance_criteria",
    "isUrgent": "is_urgent",
    "reportCycle": "report_cycle",
    "collaboratorEmployeeNos": "collaborators",
}

NODE_FIELD_ALIASES = {
    "clientNodeId": "client_node_id",
    "nodeOrder": "node_order",
    "nodeName": "node_name",
    "actionDetail": "action_detail",
    "toolsOrMaterials": "tools_or_materials",
    "ownerEmployeeNo": "owner_employee_no",
    "collaboratorEmployeeNos": "collaborators",
    "plannedStartTime": "planned_start_time",
    "plannedDeadline": "planned_deadline",
    "estimatedHours": "estimated_hours",
    "deliverable": "deliverable",
    "acceptanceCriteria": "acceptance_criteria",
}

DEPENDENCY_FIELD_ALIASES = {
    "predecessorClientNodeId": "predecessor_client_node_id",
    "successorClientNodeId": "successor_client_node_id",
    "predecessorNodeId": "predecessor_client_node_id",
    "successorNodeId": "successor_client_node_id",
    "dependencyType": "dependency_type",
    "reason": "reason",
}

LIST_FIELD_ALIASES = {
    "taskName": "task_name",
    "taskDescription": "task_description",
    "mainAssigneeEmployeeNo": "main_assignee_employee_no",
    "reportToEmployeeNo": "report_to_employee_no",
    "reviewerEmployeeNo": "reviewer_employee_no",
    "collaboratorEmployeeNos": "collaborators",
    "deadline": "deadline",
    "taskWeight": "task_weight",
    "estimatedHours": "estimated_hours",
    "performanceMetric": "performance_metric",
    "acceptanceCriteria": "acceptance_criteria",
}


class OpenAICompatibleTaskAgentProvider:
    """Task agent adapter for OpenAI-compatible chat completion APIs.

    The adapter calls the model only on the backend and returns structured suggestions.
    It never confirms, publishes, or approves tasks.
    """

    uses_structured_context = True

    def __init__(
        self,
        *,
        api_key: SecretStr,
        base_url: str,
        model: str,
        prompt_path: Path = DEFAULT_PROMPT_PATH,
        timeout_seconds: int = 30,
        completion_client: CompletionClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._prompt_path = prompt_path
        self._timeout_seconds = timeout_seconds
        self._completion_client = completion_client

    @classmethod
    def from_settings(cls, settings: Settings) -> OpenAICompatibleTaskAgentProvider:
        if settings.ai_api_key is None:
            raise ValueError("AI_API_KEY is required")
        if settings.ai_base_url is None:
            raise ValueError("AI_BASE_URL is required")
        if settings.ai_model is None:
            raise ValueError("AI_MODEL is required")
        return cls(
            api_key=settings.ai_api_key,
            base_url=settings.ai_base_url,
            model=settings.ai_model,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )

    def extract(
        self,
        text: str,
        context: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        agent_context = dict(context or {})
        if "input" not in agent_context:
            agent_context["input"] = {
                "inputType": "text",
                "rawText": text,
                "asrText": "",
                "attachmentTexts": [],
            }
        raw_result = self._complete(agent_context)
        return self._normalize_agent_result(raw_result, context=agent_context)

    def decompose(self, extracted: Mapping[str, object]) -> dict[str, object]:
        agent_context = dict(extracted)
        agent_context.setdefault("mode", "task_decomposition")
        if "input" not in agent_context:
            agent_context["input"] = {
                "inputType": "planning_context",
                "rawText": json.dumps(extracted, ensure_ascii=False, default=str),
                "asrText": "",
                "attachmentTexts": [],
            }
        raw_result = self._complete(agent_context)
        normalized = self._normalize_agent_result(raw_result, context=agent_context)[
            "extracted_json"
        ]
        nodes = normalized.get("nodes")
        dependencies = normalized.get("dependencies")
        return {
            "nodes": list(nodes) if isinstance(nodes, list) else [],
            "dependencies": list(dependencies) if isinstance(dependencies, list) else [],
        }

    def _complete(self, agent_context: Mapping[str, object]) -> Mapping[str, object]:
        messages = [
            {"role": "system", "content": self._prompt_path.read_text(encoding="utf-8")},
            {
                "role": "user",
                "content": json.dumps(agent_context, ensure_ascii=False, default=str),
            },
        ]
        if self._completion_client is not None:
            response = self._completion_client(messages)
        else:
            response = self._chat_completion(messages)
        content = self._message_content(response)
        parsed = self._parse_json_content(content)
        if not isinstance(parsed, Mapping):
            raise ValueError("AI provider returned a non-object JSON payload")
        return parsed

    def _chat_completion(self, messages: list[dict[str, str]]) -> Mapping[str, object]:
        endpoint = self._base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            endpoint,
            data=request_body,
            headers={
                "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self._timeout_seconds) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            raise RuntimeError(f"AI provider HTTP request failed with status {exc.code}") from exc
        except error.URLError as exc:
            raise RuntimeError("AI provider HTTP request failed") from exc
        parsed = json.loads(body)
        if not isinstance(parsed, Mapping):
            raise ValueError("AI provider HTTP response was not a JSON object")
        return parsed

    @staticmethod
    def _message_content(response: Mapping[str, object]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, Sequence) or not choices:
            raise ValueError("AI provider response did not include choices")
        first = choices[0]
        if not isinstance(first, Mapping):
            raise ValueError("AI provider choice was invalid")
        message = first.get("message")
        if not isinstance(message, Mapping):
            raise ValueError("AI provider choice did not include a message")
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, Sequence):
            parts: list[str] = []
            for item in content:
                if isinstance(item, Mapping) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            if parts:
                return "".join(parts)
        raise ValueError("AI provider message content was invalid")

    @staticmethod
    def _parse_json_content(content: str) -> object:
        stripped = content.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            start = stripped.find("{")
            while start >= 0:
                try:
                    parsed, _ = decoder.raw_decode(stripped[start:])
                    return parsed
                except json.JSONDecodeError:
                    start = stripped.find("{", start + 1)
            raise

    def _normalize_agent_result(
        self,
        result: Mapping[str, object],
        *,
        context: Mapping[str, object],
    ) -> dict[str, object]:
        task_draft = result.get("taskDraft") or result.get("task_draft") or result
        draft = (
            _normalize_mapping(task_draft, FIELD_ALIASES)
            if isinstance(task_draft, Mapping)
            else {}
        )
        normalized: dict[str, object] = {"agent_result": _plain_json(result)}
        normalized.update(draft)
        normalized["nodes"] = self._normalize_nodes(result.get("nodes"))
        normalized["dependencies"] = self._normalize_dependencies(result.get("dependencies"))
        normalized.setdefault("task_source", "ai_intake")
        normalized.setdefault("acceptance_criteria", _acceptance_criteria(result))

        answers = context.get("answers")
        if isinstance(answers, Mapping):
            normalized.update(_normalize_mapping(answers, FIELD_ALIASES))

        missing = _normalize_field_list(result.get("missingFields") or result.get("missing_fields"))
        low_confidence = _normalize_field_list(
            result.get("lowConfidenceFields") or result.get("low_confidence_fields")
        )
        self._enforce_candidate_users(normalized, missing, low_confidence, context)
        confirm_questions = _normalize_questions(
            result.get("confirmQuestions") or result.get("confirm_questions")
        )
        return {
            "extracted_json": normalized,
            "missing_fields": _unique(missing),
            "low_confidence_fields": _unique(low_confidence),
            "confirm_questions": confirm_questions,
            "confidence_score": _confidence_score(
                result.get("confidenceScore") or result.get("confidence_score")
            ),
        }

    @staticmethod
    def _normalize_nodes(value: object) -> list[dict[str, object]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        nodes: list[dict[str, object]] = []
        for index, item in enumerate(value, start=1):
            if not isinstance(item, Mapping):
                continue
            normalized = _normalize_mapping(item, NODE_FIELD_ALIASES)
            normalized.setdefault("client_node_id", f"draft-node-{index}")
            normalized.setdefault("node_order", index)
            if "collaborators" not in normalized:
                normalized["collaborators"] = []
            if "acceptance_criteria" not in normalized:
                normalized["acceptance_criteria"] = normalized.get("deliverable") or ""
            nodes.append(normalized)
        return nodes

    @staticmethod
    def _normalize_dependencies(value: object) -> list[dict[str, object]]:
        if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
            return []
        dependencies: list[dict[str, object]] = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            normalized = _normalize_mapping(item, DEPENDENCY_FIELD_ALIASES)
            normalized.setdefault("dependency_type", "finish_to_start")
            dependencies.append(normalized)
        return dependencies

    @staticmethod
    def _enforce_candidate_users(
        normalized: dict[str, object],
        missing: list[str],
        low_confidence: list[str],
        context: Mapping[str, object],
    ) -> None:
        allowed = _allowed_employee_numbers(context)
        if not allowed:
            return
        for field in (
            "main_assignee_employee_no",
            "report_to_employee_no",
            "reviewer_employee_no",
        ):
            value = normalized.get(field)
            if isinstance(value, str) and value and value not in allowed:
                normalized[field] = None
                missing.append(field)
                low_confidence.append(field)
        collaborators = normalized.get("collaborators")
        if isinstance(collaborators, Sequence) and not isinstance(
            collaborators, (str, bytes, bytearray)
        ):
            normalized["collaborators"] = [item for item in collaborators if str(item) in allowed]
        for node in normalized.get("nodes", []):
            if not isinstance(node, dict):
                continue
            owner = node.get("owner_employee_no")
            if isinstance(owner, str) and owner and owner not in allowed:
                node["owner_employee_no"] = None
            node_collaborators = node.get("collaborators")
            if isinstance(node_collaborators, Sequence) and not isinstance(
                node_collaborators, (str, bytes, bytearray)
            ):
                node["collaborators"] = [
                    item for item in node_collaborators if str(item) in allowed
                ]


def _normalize_mapping(
    value: Mapping[str, object],
    aliases: Mapping[str, str],
) -> dict[str, object]:
    normalized: dict[str, object] = {}
    for key, item in value.items():
        normalized[aliases.get(str(key), str(key))] = _plain_json(item)
    return normalized


def _normalize_field_list(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    return [LIST_FIELD_ALIASES.get(str(item), str(item)) for item in value]


def _normalize_questions(value: object) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return []
    questions: list[str] = []
    for item in value:
        if isinstance(item, str):
            questions.append(item)
        elif isinstance(item, Mapping):
            question = item.get("question")
            if isinstance(question, str):
                questions.append(question)
    return questions


def _confidence_score(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _acceptance_criteria(result: Mapping[str, object]) -> str:
    confirmation = result.get("taskConfirmation") or result.get("task_confirmation")
    if isinstance(confirmation, Mapping):
        summary = confirmation.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    return "User must confirm the task information before publishing."


def _allowed_employee_numbers(context: Mapping[str, object]) -> set[str]:
    allowed: set[str] = set()
    current_user = context.get("currentUser")
    if isinstance(current_user, Mapping) and current_user.get("employeeNo"):
        allowed.add(str(current_user["employeeNo"]))
    candidates = context.get("candidateUsers")
    if isinstance(candidates, Sequence) and not isinstance(candidates, (str, bytes, bytearray)):
        for candidate in candidates:
            if isinstance(candidate, Mapping) and candidate.get("employeeNo"):
                allowed.add(str(candidate["employeeNo"]))
    return allowed


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _plain_json(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _plain_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_plain_json(item) for item in value]
    return value
