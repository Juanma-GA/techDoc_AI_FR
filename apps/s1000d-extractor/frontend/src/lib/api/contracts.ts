import type { components } from "../../types/api";

type NamedFields<T> = {
  [K in keyof T as string extends K ? never : number extends K ? never : K]: T[K];
};
export type Schemas = {
  [K in keyof components["schemas"]]: NamedFields<components["schemas"][K]>;
};
