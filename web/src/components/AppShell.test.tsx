import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { expect, it } from "vitest";

import { renderPage } from "../test/test-utils";
import { AppShell } from "./AppShell";

it("uses the app-layer shell and shared bottom navigation", () => {
  renderPage(
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<p>内容</p>} />
      </Route>
    </Routes>,
    { route: "/" },
  );

  const shell = screen.getByTestId("app-shell");
  const navigation = within(shell).getByRole("navigation", { name: "底部导航" });

  expect(screen.getByRole("heading", { name: "页面不存在" })).toBeInTheDocument();
  expect(within(navigation).getByRole("button", { name: "工作台" })).toBeInTheDocument();
  expect(within(navigation).getByRole("button", { name: "创建" })).toBeInTheDocument();
});
