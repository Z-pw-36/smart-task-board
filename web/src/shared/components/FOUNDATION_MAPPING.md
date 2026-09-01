# DEV-01 HTML Foundation Mapping

Source: `docs/reference/02-第二版-智能任务看板前端.html`

| HTML visual pattern | React shared component | DEV-01 decision |
|---|---|---|
| `.card`, `.metric-card`, `.detail-panel`, `.form-section`, `.state-card` | `Card` | Shared surface only; business cards stay in later feature layers. |
| `.badge`, `.badge.green`, `.badge.orange`, `.badge.red`, `.badge.gray` | `Badge` | Visual tones only; no task status enum mapping in shared code. |
| `.btn.primary`, `.btn.secondary`, `.btn.danger`, `.link-btn`, `.icon-btn`, `.round-btn` | `Button` | Primary/secondary/ghost/danger/icon/loading/disabled variants. |
| `.field`, `.input`, `.textarea`, `.select` | `Input` | Shared text input with label/helper/error; business validation remains feature-owned. |
| `.progress`, `.pressure .progress`, `.progress-track` | `Progress` | Neutral percentage primitive. |
| `.topbar`, `.detail-page-head`, `.section-head` | `TopBar`, typography primitives | Header layout and type hierarchy only; route back behavior later. |
| `.bottom-nav`, `.nav-item` | `BottomNavigation` | Layout, safe area, active/inactive appearance; no DEV-02 route wiring. |
| `.overlay`, `.sheet`, `.sheet-head`, `.close` | `Sheet` | Accessible modal bottom sheet with close, Escape, overlay click. |
| `.dialog-wrap`, `.dialog`, reason/confirm dialogs | `Dialog` | Accessible modal dialog shell; submit logic remains feature-owned. |
| `.toast` | `ToastProvider`, `useToast` | Neutral toast surface/call ability; no business success messages. |
| Loading placeholders | `Skeleton` | Deterministic loading primitive. |
| Empty cards/states | `EmptyState` | Neutral empty state, optional action. |
| Error cards/states | `ErrorState` | Neutral error state, optional action. |
| `.title`, `.section-title`, `.task-name`, `.subtle`, metric numbers, labels | `Typography` and CSS tokens | Centralized typography hierarchy. |

HTML effective shared foundation primitives mapped: 14 / 14.

Unmapped shared foundation primitives: 0.
