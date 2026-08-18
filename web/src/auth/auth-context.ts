import { createContext } from "react";

import type { CurrentUser } from "../api/types";

export interface AuthValue {
  user: CurrentUser | null;
  loading: boolean;
  login(employeeNo: string): Promise<void>;
  logout(): void;
}

export const AuthContext = createContext<AuthValue | null>(null);
