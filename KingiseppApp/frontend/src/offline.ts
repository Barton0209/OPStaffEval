import Dexie, { type Table } from "dexie";
import { apiSaveEvaluation } from "./api";

export type OutboxItem = {
  id?: number;
  kind: "assignment" | "urgent";
  targetId: number;
  submit: boolean;
  body: Record<string, unknown>;
  createdAt: number;
};

class OfflineDB extends Dexie {
  outbox!: Table<OutboxItem, number>;

  constructor() {
    super("kingisepp_offline");
    this.version(1).stores({ outbox: "++id, createdAt" });
  }
}

const db = new OfflineDB();

export async function enqueueOutbox(item: OutboxItem) {
  await db.outbox.add(item);
}

export async function listOutbox() {
  return db.outbox.orderBy("createdAt").toArray();
}

export async function flushOutbox(): Promise<number> {
  const items = await listOutbox();
  let ok = 0;
  for (const item of items) {
    try {
      const res = await apiSaveEvaluation(item.kind, item.targetId, item.body, item.submit);
      if (!res.conflict && item.id != null) {
        await db.outbox.delete(item.id);
        ok += 1;
      }
    } catch {
      break;
    }
  }
  return ok;
}
