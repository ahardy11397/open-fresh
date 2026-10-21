import React from "react";
import type { Settings } from "../types";

interface SettingsViewProps {
  settings: Settings | null;
  onRefresh?: () => void;
  onError?: (msg: string) => void;
}

export const SettingsView: React.FC<SettingsViewProps> = () => {
  return (
    <div className="surface-placeholder">
      <h2>Household Settings</h2>
      <p>Household preferences and configuration will be expanded in Task 3.</p>
    </div>
  );
};
