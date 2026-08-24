"use client";

import { useEffect, useState } from "react";

import { DemoRole, getRole, setRole } from "../lib/demoAuth";
import { t } from "../lib/i18n";

const ROLES: DemoRole[] = ["creator", "institution", "admin"];

export function RoleSwitcher() {
  const [role, setLocalRole] = useState<DemoRole>("creator");

  useEffect(() => {
    setLocalRole(getRole());
  }, []);

  function onChange(next: DemoRole) {
    setRole(next);
    setLocalRole(next);
    // Roles change what the API returns, so re-fetch the whole page.
    window.location.reload();
  }

  return (
    <label className="role-switcher">
      <span>Role</span>
      <select
        value={role}
        onChange={(event) => onChange(event.target.value as DemoRole)}
      >
        {ROLES.map((value) => (
          <option key={value} value={value}>
            {t(`role.${value}`)}
          </option>
        ))}
      </select>
    </label>
  );
}
