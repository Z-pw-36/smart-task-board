/**
 * Feature: DEV-01 shared primitive component tests.
 * Responsibilities: verify accessibility, touch targets, close behavior, and neutral rendering.
 * Does not own: business page behavior, API calls, or task workflow state.
 * Plan task: DEV-01.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Badge, BottomNavigation, Button, Card, Dialog, EmptyState, ErrorState, Input, Progress, Sheet, Skeleton, ToastProvider, TopBar, Typography, useToast } from "../index";

function ToastTrigger() {
  const { showToast } = useToast();
  return <Button onClick={() => showToast("中性提示")}>显示提示</Button>;
}

describe("DEV-01 shared mobile primitives", () => {
  it("renders neutral card, typography, badge, progress, empty and error primitives", () => {
    render(
      <Card title="基础卡片">
        <Typography variant="metric">86</Typography>
        <Badge tone="success">稳定标签</Badge>
        <Progress label="完成度" value={72} />
        <Skeleton width={120} />
        <EmptyState title="暂无内容" detail="稍后会显示新的内容。" />
        <ErrorState detail="请稍后重试。" />
      </Card>,
    );

    expect(screen.getByRole("heading", { name: "基础卡片" })).toBeInTheDocument();
    expect(screen.getByText("稳定标签")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "完成度" })).toHaveAttribute("aria-valuenow", "72");
    expect(screen.getByRole("status", { name: "正在加载" })).toBeInTheDocument();
    expect(screen.getByText("暂无内容")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("请稍后重试。");
  });

  it("supports button accessible names, disabled/loading states, and 44px touch classes", async () => {
    const onClick = vi.fn();
    render(
      <>
        <Button onClick={onClick}>主要操作</Button>
        <Button aria-label="刷新" iconOnly variant="ghost">↻</Button>
        <Button loading>提交中</Button>
      </>,
    );

    await userEvent.click(screen.getByRole("button", { name: "主要操作" }));
    expect(onClick).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "刷新" })).toHaveClass("stb-button--icon");
    expect(screen.getByRole("button", { name: /提交中/ })).toBeDisabled();
  });

  it("links input label, helper text, error text, and disabled state", () => {
    render(<Input label="标题" placeholder="请输入标题" helperText="最多 20 字" error="标题不能为空" disabled />);

    const input = screen.getByLabelText("标题");
    expect(input).toHaveAttribute("placeholder", "请输入标题");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("最多 20 字 标题不能为空");
    expect(input).toBeDisabled();
  });

  it("renders top bar and bottom navigation without route wiring", async () => {
    const onSelect = vi.fn();
    render(
      <>
        <TopBar title="组件基线" subtitle="确定性测试" actions={<Button aria-label="更多" iconOnly variant="secondary">…</Button>} />
        <BottomNavigation
          activeId="home"
          onSelect={onSelect}
          items={[
            { id: "home", label: "首页", icon: "⌂" },
            { id: "notice", label: "通知", icon: "!" },
          ]}
        />
      </>,
    );

    expect(screen.getByRole("heading", { name: "组件基线" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "底部导航" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /通知/ }));
    expect(onSelect).toHaveBeenCalledWith("notice");
  });

  it("closes sheet and dialog through accessible controls, Escape, and overlay click", async () => {
    const closeSheet = vi.fn();
    const closeDialog = vi.fn();
    const { rerender } = render(<Sheet open title="筛选抽屉" onClose={closeSheet}><p>抽屉内容</p></Sheet>);

    expect(screen.getByRole("dialog", { name: "筛选抽屉" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "关闭抽屉" })).toHaveFocus();
    await userEvent.click(screen.getByRole("button", { name: "关闭抽屉" }));
    expect(closeSheet).toHaveBeenCalledTimes(1);

    rerender(<Dialog open title="确认弹窗" onClose={closeDialog}><p>弹窗内容</p></Dialog>);
    expect(screen.getByRole("button", { name: "关闭弹窗" })).toHaveFocus();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(closeDialog).toHaveBeenCalledTimes(1);

    rerender(<Dialog open title="确认弹窗" onClose={closeDialog}><p>弹窗内容</p></Dialog>);
    fireEvent.mouseDown(screen.getByRole("presentation"));
    expect(closeDialog).toHaveBeenCalledTimes(2);
  });

  it("provides neutral toast calls without business messages", async () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    );

    await userEvent.click(screen.getByRole("button", { name: "显示提示" }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("中性提示"));
  });
});
