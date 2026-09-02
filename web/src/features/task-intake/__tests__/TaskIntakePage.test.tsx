import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, renderPage } from "../../../test/test-utils";
import type { TaskIntakeResponse } from "../../../api/types";
import { TaskIntakePage } from "../TaskIntakePage";

const intake: TaskIntakeResponse = {
  input_id: "11111111-1111-4111-8111-111111111111",
  input_type: "text",
  raw_text: "请完成门店上线方案",
  asr_text: null,
  source_channel: "web",
  submitted_by_employee_no: "E-CREATOR",
  submitted_at: "2026-09-02T04:00:00Z",
  extraction_id: "22222222-2222-4222-8222-222222222222",
  extracted_json: {
    task_name: "门店上线方案",
    task_description: "完成门店上线方案并提交验收材料",
    task_goal: "门店上线准备完成",
    main_assignee_employee_no: "E-ASSIGNEE",
    report_to_employee_no: "E-CREATOR",
    reviewer_employee_no: "E-CREATOR",
    deadline: "2026-09-08T10:00:00+08:00",
    task_weight: 3,
    acceptance_criteria: "上线材料齐全",
  },
  missing_fields: [],
  low_confidence_fields: [],
  confirm_questions: [],
  confidence_score: "0.95",
  job_status: "succeeded",
  retry_after_seconds: null,
};

const missingIntake: TaskIntakeResponse = {
  ...intake,
  extraction_id: "33333333-3333-4333-8333-333333333333",
  extracted_json: {
    task_name: "门店上线方案",
    task_description: "完成门店上线方案",
    task_weight: 3,
  },
  missing_fields: ["main_assignee_employee_no", "deadline"],
  low_confidence_fields: ["deadline"],
  confirm_questions: ["请确认主承办人。", "请确认截止时间。"],
  confidence_score: "0.6",
};

function mockIntakeFetch(response: TaskIntakeResponse = intake) {
  const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
    const value = String(url);
    const method = init?.method || "GET";
    if (value.includes("/api/v1/task-inputs") && method === "POST") {
      return jsonResponse(response, 201);
    }
    if (value.includes("/api/v1/task-inputs/") && value.includes("/extraction")) {
      return jsonResponse(response);
    }
    return jsonResponse({}, 404);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("TaskIntakePage", () => {
  afterEach(() => {
    sessionStorage.clear();
    vi.unstubAllGlobals();
  });

  it("submits text input and renders the structured extraction without creating a task", async () => {
    const fetchMock = mockIntakeFetch();
    const user = userEvent.setup();
    renderPage(<TaskIntakePage />);

    await user.type(screen.getByLabelText("任务原文"), "请完成门店上线方案");
    await user.click(screen.getByRole("button", { name: "识别字段" }));

    expect(await screen.findByText("字段识别已完成。")).toBeInTheDocument();
    expect(screen.getByText("门店上线方案")).toBeInTheDocument();
    expect(screen.getByText("上线材料齐全")).toBeInTheDocument();
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as Record<string, unknown>;
    expect(requestBody).toMatchObject({
      input_type: "text",
      raw_text: "请完成门店上线方案",
      source_channel: "web",
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/v1/tasks"))).toBe(false);
  });

  it("shows missing fields and submits clarification text for a new extraction round", async () => {
    let latest: TaskIntakeResponse = missingIntake;
    const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const value = String(url);
      const method = init?.method || "GET";
      if (value.endsWith("/api/v1/task-inputs") && method === "POST") {
        return jsonResponse(latest, 201);
      }
      if (value.includes("/clarifications") && method === "POST") {
        latest = { ...intake, extraction_id: "44444444-4444-4444-8444-444444444444" };
        return jsonResponse(latest);
      }
      if (value.includes("/extraction")) return jsonResponse(latest);
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage(<TaskIntakePage />);

    await user.type(screen.getByLabelText("任务原文"), "门店上线方案缺少人员和日期");
    await user.click(screen.getByRole("button", { name: "识别字段" }));

    expect(await screen.findByText("需要补充关键信息。")).toBeInTheDocument();
    expect(screen.getByText("主承办人、截止时间")).toBeInTheDocument();
    await user.type(screen.getByLabelText("补充说明"), "assignee:E-ASSIGNEE deadline:2026-09-08T10:00:00+08:00");
    await user.click(screen.getByRole("button", { name: "提交补充" }));

    expect(await screen.findByText("补充信息已合并。")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/clarifications"))).toBe(true);
  });

  it("retries existing extraction and surfaces safe provider errors", async () => {
    const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const value = String(url);
      const method = init?.method || "GET";
      if (value.endsWith("/api/v1/task-inputs") && method === "POST") return jsonResponse(intake, 201);
      if (value.includes("/extraction") && method === "GET") return jsonResponse(intake);
      if (value.includes("/extract") && method === "POST") {
        return jsonResponse({ error: { code: "business_validation_error", message: "AI provider is rate limited; retry later", details: {} } }, 422);
      }
      return jsonResponse({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderPage(<TaskIntakePage />);

    await user.type(screen.getByLabelText("任务原文"), "请完成门店上线方案");
    await user.click(screen.getByRole("button", { name: "识别字段" }));
    await screen.findByText("字段识别已完成。");
    await user.click(screen.getByRole("button", { name: "重试识别" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("AI provider is rate limited; retry later");
  });

  it("falls back to text when browser voice is unsupported", async () => {
    renderPage(<TaskIntakePage />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "语音输入" }));

    expect(screen.getByRole("alert")).toHaveTextContent("当前浏览器不支持语音输入");
    expect(screen.getByLabelText("任务原文")).toHaveFocus();
  });

  it("falls back to text when microphone permission is denied", async () => {
    class DeniedRecognition {
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((event: unknown) => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        this.onerror?.({ error: "not-allowed" });
        this.onend?.();
      }
    }
    vi.stubGlobal("SpeechRecognition", DeniedRecognition);
    renderPage(<TaskIntakePage />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "语音输入" }));

    expect(screen.getByRole("alert")).toHaveTextContent("未获得麦克风权限");
  });

  it("submits browser voice transcription as voice input without audio storage", async () => {
    class SuccessfulRecognition {
      lang = "";
      interimResults = false;
      continuous = false;
      onresult: ((event: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null = null;
      onerror: ((event: unknown) => void) | null = null;
      onend: (() => void) | null = null;
      start() {
        this.onresult?.({ resultIndex: 0, results: [[{ transcript: "语音生成任务" }]] });
        this.onend?.();
      }
    }
    const fetchMock = mockIntakeFetch({ ...intake, input_type: "voice", raw_text: "语音生成任务", asr_text: "语音生成任务" });
    vi.stubGlobal("SpeechRecognition", SuccessfulRecognition);
    renderPage(<TaskIntakePage />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "语音输入" }));
    await user.click(screen.getByRole("button", { name: "识别字段" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const requestBody = JSON.parse(String(fetchMock.mock.calls[0][1]?.body)) as Record<string, unknown>;
    expect(requestBody.input_type).toBe("voice");
    expect(requestBody.raw_text).toBe("语音生成任务");
    expect(requestBody).not.toHaveProperty("voice_file_url");
  });
});
