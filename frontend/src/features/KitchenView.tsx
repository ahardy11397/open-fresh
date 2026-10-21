import React from "react";

interface KitchenViewProps {
  onError?: (msg: string) => void;
}

export const KitchenView: React.FC<KitchenViewProps> = () => {
  return (
    <div className="surface-placeholder">
      <h2>Kitchen Inventory</h2>
      <p>Pantry, fridge, and freezer inventory management will be expanded in Task 3.</p>
    </div>
  );
};
