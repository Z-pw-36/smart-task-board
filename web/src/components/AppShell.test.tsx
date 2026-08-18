import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { expect, it } from "vitest";

import { renderPage } from "../test/test-utils";
import { AppShell } from "./AppShell";

it("provides both desktop and mobile semantic navigation", () => {
  renderPage(<Routes><Route element={<AppShell />}><Route index element={<p>内容</p>} /></Route></Routes>);

  const sidebar = screen.getByRole("complementary", { name: "主导航" });
  const brandLink = within(sidebar).getByRole("link", { name: "SmartTaskBoard 首页" });
  const desktopNavigation = within(sidebar).getByRole("navigation");
  const mobileNavigation = screen.getByRole("navigation", { name: "移动端主导航" });

  expect(brandLink).toHaveAttribute("href", "/");
  expect(within(desktopNavigation).getByRole("link", { name: /首页$/ })).toHaveAttribute("href", "/");
  expect(within(mobileNavigation).getByRole("link", { name: /首页$/ })).toHaveAttribute("href", "/");
  expect(within(desktopNavigation).getByRole("link", { name: /创建$/ })).toHaveAttribute("href", "/tasks/new");
  expect(within(mobileNavigation).getByRole("link", { name: /创建$/ })).toHaveAttribute("href", "/tasks/new");
});
