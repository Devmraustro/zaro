export const PRODUCT_TYPES = [
  { value: "dining_table", label: "Dining Table" },
  { value: "coffee_table", label: "Coffee Table" },
  { value: "chair", label: "Chair" },
  { value: "shelf", label: "Shelf / Storage" },
  { value: "desk", label: "Desk" },
  { value: "custom_metalwork", label: "Custom Metalwork" },
  { value: "other", label: "Other" },
] as const;

export type ProductType = (typeof PRODUCT_TYPES)[number]["value"];

export const DEFAULT_PRODUCT_TYPE: ProductType = "dining_table";

export const PRODUCT_TYPE_VALUES: readonly ProductType[] = PRODUCT_TYPES.map(
  (option) => option.value,
);