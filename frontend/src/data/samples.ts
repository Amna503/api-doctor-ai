import oldSpec from "./sample_old.json";
import newSpec from "./sample_new.json";
import consumers from "./sample_consumers.json";
import type { Consumer } from "../types";

export const sampleOld = oldSpec as Record<string, unknown>;
export const sampleNew = newSpec as Record<string, unknown>;
export const sampleConsumers = consumers as Consumer[];

export const sampleOldText = JSON.stringify(oldSpec, null, 2);
export const sampleNewText = JSON.stringify(newSpec, null, 2);
export const sampleConsumersText = JSON.stringify(consumers, null, 2);

export const sampleDescriptor = {
  name: "Acme Payments v1 → v2",
  description:
    "Legacy routes removed, money moved to minor units, OAuth added, and a customer response field renamed. Three declared consumers.",
};
