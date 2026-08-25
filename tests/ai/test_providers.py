from __future__ import annotations

import json

from pydantic import SecretStr

from app.ai.providers import OpenAICompatibleTaskAgentProvider


def test_openai_compatible_provider_normalizes_agent_json(tmp_path) -> None:
    prompt_path = tmp_path / "task_agent.md"
    prompt_path.write_text("Return JSON suggestions only.", encoding="utf-8")
    captured: dict[str, object] = {}

    def completion_client(messages):
        captured["call_count"] = int(captured.get("call_count", 0)) + 1
        captured["messages"] = messages
        content = {
            "confidenceScore": 0.86,
            "taskDraft": {
                "taskName": "门店上线方案",
                "taskDescription": "完成门店上线方案。",
                "mainAssigneeEmployeeNo": "E1003",
                "reportToEmployeeNo": "E1001",
                "reviewerEmployeeNo": "E1001",
                "deadline": "2026-08-28T18:00:00+08:00",
                "taskWeight": 3,
                "collaboratorEmployeeNos": [],
            },
            "missingFields": [],
            "lowConfidenceFields": ["deadline"],
            "confirmQuestions": [
                {"field": "deadline", "question": "请确认截止时间。"},
            ],
            "nodes": [
                {
                    "clientNodeId": "draft-node-1",
                    "nodeName": "确认上线范围",
                    "actionDetail": "确认门店、系统模块和业务范围。",
                    "toolsOrMaterials": "门店清单",
                    "ownerEmployeeNo": "E1003",
                    "collaboratorEmployeeNos": [],
                    "deliverable": "上线范围确认单",
                }
            ],
            "dependencies": [],
            "taskConfirmation": {"summary": "请确认任务信息和节点拆解。"},
        }
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(content, ensure_ascii=False),
                    }
                }
            ]
        }

    provider = OpenAICompatibleTaskAgentProvider(
        api_key=SecretStr("unit-secret-key"),
        base_url="https://unit.invalid/v1",
        model="unit-model",
        prompt_path=prompt_path,
        completion_client=completion_client,
    )

    result = provider.extract(
        "下周五前完成门店上线方案。",
        context={
            "input": {"inputType": "text", "rawText": "下周五前完成门店上线方案。"},
            "currentUser": {"employeeNo": "E1001", "name": "林知"},
            "candidateUsers": [{"employeeNo": "E1003", "name": "王敏"}],
            "performanceMetrics": [],
            "rules": {"timezone": "Asia/Shanghai"},
        },
    )

    extracted = result["extracted_json"]
    assert extracted["task_name"] == "门店上线方案"
    assert extracted["main_assignee_employee_no"] == "E1003"
    assert extracted["acceptance_criteria"] == "请确认任务信息和节点拆解。"
    assert extracted["nodes"][0]["node_name"] == "确认上线范围"
    assert result["low_confidence_fields"] == ["deadline"]
    assert result["confirm_questions"] == ["请确认截止时间。"]
    assert provider.decompose(extracted)["nodes"][0]["client_node_id"] == "draft-node-1"
    assert captured["call_count"] == 2
    assert "unit-secret-key" not in repr(provider)
    assert captured["messages"][0]["content"] == "Return JSON suggestions only."
