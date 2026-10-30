import { describe, expect, it } from "vitest";
import { ValidationQueue, VALIDATION_BATCH_SIZE } from "./validationQueue";

describe("validation batching", () => {
  it("runs at most two batches and continues after a failed batch", async () => {
    const queue = new ValidationQueue(2);
    let active = 0;
    let maximum = 0;
    let processed = 0;
    const results = await Promise.allSettled(Array.from({ length: 5 }, (_, index) =>
      queue.enqueue(async () => {
        active += 1;
        maximum = Math.max(maximum, active);
        await new Promise((resolve) => setTimeout(resolve, 5));
        active -= 1;
        processed += 1;
        if (index === 1) throw new Error("Synthetic validation failure.");
        return index;
      }),
    ));
    expect(maximum).toBe(2);
    expect(processed).toBe(5);
    expect(results.filter((result) => result.status === "rejected")).toHaveLength(1);
    expect(VALIDATION_BATCH_SIZE).toBe(20);
  });
});
