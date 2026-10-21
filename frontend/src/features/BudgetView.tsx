import React from "react";

interface BudgetViewProps {
  weekStart: string;
  onError?: (msg: string) => void;
}

export const BudgetView: React.FC<BudgetViewProps> = ({ weekStart }) => {
  return (
    <div className="surface-placeholder">
      <h2>Budget & Prices</h2>
      <p>Weekly budget for week {weekStart} and price library will be expanded in Task 3.</p>
    </div>
  );
};
