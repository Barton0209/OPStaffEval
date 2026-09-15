import Dexie, { type Table } from "dexie";
import { apiSaveEvaluation, type SaveEvaluationResult } from "./api";

export type OutboxItem = {
  id?: number;
  kind: "assignment" | "urgent";
  targetId: number;
  submit: boolean;
  body: Record<string, unknown>;
  createdAt: number;
};

export type FlushResult = {
  ok: number;
  conflicts: { item: OutboxItem; response: SaveEvaluationResult }[];
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

export async function flushOutbox(): Promise<FlushResult> {
  const items = await listOutbox();
  let ok = 0;
  const conflicts: FlushResult["conflicts"] = [];
  for (const item of items) {
    try {
      const res = await apiSaveEvaluation(item.kind, item.targetId, item.body, item.submit);
      // Элемент удаляется из очереди в любом случае (отправлен или устарел из-за конфликта).
      if (item.id != null) {
        await db.outbox.delete(item.id);
      }
      if (res.conflict) {
        conflicts.push({ item, response: res });
      } else {
        ok += 1;
      }
    } catch {
      break; // нет сети — пробуем в следующий раз
    }
  }
  return { ok, conflicts };
}
