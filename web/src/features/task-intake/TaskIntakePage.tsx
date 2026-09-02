/**
 * Feature: DEV-07 AI task intake.
 * Responsibilities: collect text/voice task descriptions, request backend field extraction, show clarification and retry states.
 * Does not own: formal task creation, sending, node decomposition, lifecycle actions, or AI provider secrets.
 * Plan task: DEV-07.
 */

import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../../api/client";
import {
  clarifyTaskInput,
  getTaskInputExtraction,
  retryTaskInputExtraction,
  submitTaskInput,
} from "../../api/endpoints";
import type { TaskIntakeResponse, TaskInputType } from "../../api/types";
import { useAuth } from "../../auth/useAuth";
import { Badge, Button, Card, ErrorState, Skeleton, TopBar, Typography } from "../../shared/components";
import "./TaskIntakePage.css";

const DRAFT_KEY = "smarttaskboard.dev07.intake-draft";
const MAX_INPUT_LENGTH = 4000;
const SLOW_HINT_MS = 60_000;

type IntakeDraft = {
  rawText: string;
  inputId: string | null;
  intake: TaskIntakeResponse | null;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<ArrayLike<{ transcript: string }>>;
};

type SpeechRecognitionErrorLike = {
  error?: string;
};

type SpeechRecognitionLike = {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop?: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

function readDraft(): IntakeDraft {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "{}") as Partial<IntakeDraft>;
    return {
      rawText: typeof parsed.rawText === "string" ? parsed.rawText : "",
      inputId: typeof parsed.inputId === "string" ? parsed.inputId : null,
      intake: isIntake(parsed.intake) ? parsed.intake : null,
    };
  } catch {
    return { rawText: "", inputId: null, intake: null };
  }
}

function writeDraft(draft: IntakeDraft) {
  sessionStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
}

function isIntake(value: unknown): value is TaskIntakeResponse {
  return typeof value === "object" && value !== null && "input_id" in value && "extraction_id" in value;
}

function formatFieldName(field: string) {
  const labels: Record<string, string> = {
    task_name: "任务名称",
    task_description: "任务描述",
    task_goal: "任务目标",
    main_assignee_employee_no: "主承办人",
    report_to_employee_no: "汇报对象",
    reviewer_employee_no: "验收人",
    deadline: "截止时间",
    task_weight: "任务权重",
    acceptance_criteria: "验收标准",
    performance_metric: "绩效指标",
  };
  return labels[field] || field;
}

function valueText(value: unknown) {
  if (value === null || value === undefined || value === "") return "待确认";
  if (Array.isArray(value)) return value.length ? value.join("、") : "无";
  return String(value);
}

function statusTone(intake: TaskIntakeResponse | null): "success" | "warning" | "neutral" {
  if (!intake) return "neutral";
  return intake.missing_fields.length || intake.low_confidence_fields.length ? "warning" : "success";
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  return error instanceof Error ? error.message : "识别未完成，请稍后重试。";
}

function useSlowHint(working: boolean) {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    if (!working) {
      setVisible(false);
      return;
    }
    const timer = window.setTimeout(() => setVisible(true), SLOW_HINT_MS);
    return () => window.clearTimeout(timer);
  }, [working]);
  return visible;
}

export function TaskIntakePage() {
  const { user } = useAuth();
  const restored = useMemo(readDraft, []);
  const [rawText, setRawText] = useState(restored.rawText);
  const [inputId, setInputId] = useState<string | null>(restored.inputId);
  const [intake, setIntake] = useState<TaskIntakeResponse | null>(restored.intake);
  const [sourceType, setSourceType] = useState<TaskInputType>("text");
  const [clarificationText, setClarificationText] = useState("");
  const [notice, setNotice] = useState("");
  const [voiceError, setVoiceError] = useState("");
  const [voiceState, setVoiceState] = useState<"idle" | "listening">("idle");
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    writeDraft({ rawText, inputId, intake });
  }, [rawText, inputId, intake]);

  const extractionQuery = useQuery({
    queryKey: ["task-input-extraction", inputId],
    queryFn: () => getTaskInputExtraction(inputId || ""),
    enabled: Boolean(inputId),
    refetchInterval: (query) => {
      const status = query.state.data?.job_status;
      return status === "pending" || status === "running" ? 1000 : false;
    },
  });

  useEffect(() => {
    if (extractionQuery.data) setIntake(extractionQuery.data);
  }, [extractionQuery.data]);

  const submitMutation = useMutation({
    mutationFn: () => {
      const text = rawText.trim();
      if (!text) throw new Error("请输入任务内容。");
      if (text.length > MAX_INPUT_LENGTH) throw new Error("任务内容不能超过 4000 字。");
      return submitTaskInput({
        input_type: sourceType,
        raw_text: text,
        source_channel: "web",
      });
    },
    onSuccess: (result) => {
      setInputId(result.input_id);
      setIntake(result);
      setNotice(result.confirm_questions.length ? "需要补充关键信息。" : "字段识别已完成。");
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  const retryMutation = useMutation({
    mutationFn: () => {
      if (!inputId) return submitMutation.mutateAsync();
      return retryTaskInputExtraction(inputId);
    },
    onSuccess: (result) => {
      setInputId(result.input_id);
      setIntake(result);
      setNotice("已重新识别字段。");
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  const clarifyMutation = useMutation({
    mutationFn: () => {
      if (!intake) throw new Error("请先完成字段识别。");
      const text = clarificationText.trim();
      if (!text) throw new Error("请输入补充说明。");
      return clarifyTaskInput(intake.input_id, { answers: { clarification_text: text } });
    },
    onSuccess: (result) => {
      setInputId(result.input_id);
      setIntake(result);
      setClarificationText("");
      setNotice(result.confirm_questions.length ? "补充信息已更新，仍需确认。" : "补充信息已合并。");
    },
    onError: (error) => setNotice(errorMessage(error)),
  });

  const working = submitMutation.isPending || retryMutation.isPending || clarifyMutation.isPending;
  const showSlowHint = useSlowHint(working);
  const draft = intake?.extracted_json || {};
  const needsClarification = Boolean(
    intake && (intake.missing_fields.length || intake.low_confidence_fields.length || intake.confirm_questions.length),
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    submitMutation.mutate();
  }

  function startVoice() {
    setVoiceError("");
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setVoiceError("当前浏览器不支持语音输入，已切换为文字输入。");
      textareaRef.current?.focus();
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = "zh-CN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let transcript = "";
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        transcript += event.results[index][0]?.transcript || "";
      }
      setSourceType("voice");
      setRawText(transcript.trim());
    };
    recognition.onerror = (event) => {
      setVoiceState("idle");
      setVoiceError(
        event.error === "not-allowed"
          ? "未获得麦克风权限，已切换为文字输入。"
          : "语音转写失败，已切换为文字输入。",
      );
      textareaRef.current?.focus();
    };
    recognition.onend = () => setVoiceState("idle");
    try {
      setVoiceState("listening");
      recognition.start();
    } catch {
      setVoiceState("idle");
      setVoiceError("语音服务暂不可用，已切换为文字输入。");
      textareaRef.current?.focus();
    }
  }

  return (
    <section className="stb-task-intake" data-testid="task-intake-page">
      <TopBar title="描述任务" subtitle={user ? `${user.name} · AI 字段识别` : "AI 字段识别"} />

      {notice && (
        <div className={notice.includes("未") || notice.includes("不能") ? "stb-task-intake-alert stb-task-intake-alert--error" : "stb-task-intake-alert"} role="status">
          {notice}
        </div>
      )}

      <Card className="stb-task-intake-panel">
        <form className="stb-task-intake-form" onSubmit={submit}>
          <label className="stb-task-intake-field">
            <span>任务原文</span>
            <textarea
              ref={textareaRef}
              aria-describedby="task-intake-count"
              value={rawText}
              maxLength={MAX_INPUT_LENGTH}
              onChange={(event) => {
                setSourceType("text");
                setRawText(event.target.value);
              }}
            />
          </label>
          <div className="stb-task-intake-form__meta">
            <span id="task-intake-count">{rawText.length}/{MAX_INPUT_LENGTH}</span>
            <Badge tone={sourceType === "voice" ? "info" : "neutral"}>{sourceType === "voice" ? "语音转写" : "文字输入"}</Badge>
          </div>
          {voiceError && <div className="stb-task-intake-alert stb-task-intake-alert--error" role="alert">{voiceError}</div>}
          {showSlowHint && <div className="stb-task-intake-alert" role="status">识别耗时较长，后台完成后可刷新结果。</div>}
          <div className="stb-task-intake-actions">
            <Button type="submit" loading={submitMutation.isPending}>识别字段</Button>
            <Button type="button" variant="secondary" onClick={startVoice} disabled={voiceState === "listening"} aria-label={voiceState === "listening" ? "正在语音输入" : "语音输入"}>
              {voiceState === "listening" ? "正在听写" : "语音输入"}
            </Button>
            <Button type="button" variant="ghost" loading={retryMutation.isPending} onClick={() => retryMutation.mutate()}>
              重试识别
            </Button>
          </div>
        </form>
      </Card>

      {extractionQuery.isLoading && (
        <Card className="stb-task-intake-panel" aria-label="正在加载识别结果">
          <Skeleton height={20} />
          <Skeleton height={20} />
        </Card>
      )}

      {intake && (
        <Card title="识别结果" className="stb-task-intake-panel">
          <div className="stb-task-intake-result-head">
            <Badge tone={statusTone(intake)}>{needsClarification ? "需要澄清" : "可确认"}</Badge>
            <Typography variant="secondary">Input {intake.input_id.slice(0, 8)} · Extraction {intake.extraction_id.slice(0, 8)}</Typography>
          </div>
          <dl className="stb-task-intake-fields">
            <div><dt>任务名称</dt><dd>{valueText(draft.task_name)}</dd></div>
            <div><dt>任务目标</dt><dd>{valueText(draft.task_goal)}</dd></div>
            <div><dt>主承办人</dt><dd>{valueText(draft.main_assignee_employee_no)}</dd></div>
            <div><dt>汇报对象</dt><dd>{valueText(draft.report_to_employee_no)}</dd></div>
            <div><dt>验收人</dt><dd>{valueText(draft.reviewer_employee_no)}</dd></div>
            <div><dt>截止时间</dt><dd>{valueText(draft.deadline)}</dd></div>
            <div><dt>任务权重</dt><dd>{valueText(draft.task_weight)}</dd></div>
            <div className="stb-task-intake-fields__wide"><dt>任务描述</dt><dd>{valueText(draft.task_description)}</dd></div>
            <div className="stb-task-intake-fields__wide"><dt>验收标准</dt><dd>{valueText(draft.acceptance_criteria)}</dd></div>
          </dl>
          <div className="stb-task-intake-review">
            <div>
              <Typography variant="label">缺失项</Typography>
              <p>{intake.missing_fields.length ? intake.missing_fields.map(formatFieldName).join("、") : "无"}</p>
            </div>
            <div>
              <Typography variant="label">低置信项</Typography>
              <p>{intake.low_confidence_fields.length ? intake.low_confidence_fields.map(formatFieldName).join("、") : "无"}</p>
            </div>
          </div>
          {intake.confirm_questions.length > 0 && (
            <ul className="stb-task-intake-questions" aria-label="追问问题">
              {intake.confirm_questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          )}
        </Card>
      )}

      {needsClarification && (
        <Card title="补充澄清" className="stb-task-intake-panel">
          <form className="stb-task-intake-form" onSubmit={(event) => { event.preventDefault(); clarifyMutation.mutate(); }}>
            <label className="stb-task-intake-field">
              <span>补充说明</span>
              <textarea
                value={clarificationText}
                onChange={(event) => setClarificationText(event.target.value)}
              />
            </label>
            <div className="stb-task-intake-actions">
              <Button type="submit" loading={clarifyMutation.isPending}>提交补充</Button>
              <Button type="button" variant="secondary" loading={retryMutation.isPending} onClick={() => retryMutation.mutate()}>
                重新识别
              </Button>
            </div>
          </form>
        </Card>
      )}

      {(extractionQuery.isError || submitMutation.isError || retryMutation.isError || clarifyMutation.isError) && (
        <ErrorState
          title="识别暂未完成"
          detail={errorMessage(extractionQuery.error || submitMutation.error || retryMutation.error || clarifyMutation.error)}
          action={<Button variant="secondary" onClick={() => retryMutation.mutate()}>重试</Button>}
        />
      )}
    </section>
  );
}
