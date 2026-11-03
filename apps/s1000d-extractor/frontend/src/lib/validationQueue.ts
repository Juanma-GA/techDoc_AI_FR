export const VALIDATION_BATCH_SIZE = 20;

export class ValidationQueue {
  private active = 0;
  private readonly pending: Array<() => void> = [];
  constructor(private readonly concurrency = 2) {
    if (!Number.isInteger(concurrency) || concurrency < 1) throw new RangeError("Invalid concurrency.");
  }
  enqueue<T>(task: () => Promise<T>): Promise<T> {
    return new Promise<T>((resolve, reject) => {
      this.pending.push(() => {
        this.active += 1;
        void Promise.resolve().then(task).then(resolve, reject).finally(() => {
          this.active -= 1;
          this.drain();
        });
      });
      this.drain();
    });
  }
  private drain() {
    while (this.active < this.concurrency && this.pending.length) this.pending.shift()?.();
  }
}
