import { createRequire } from "node:module";
import type { DatabaseSync } from "node:sqlite";
import { dirname } from "node:path";
import { mkdirSync } from "node:fs";
import { applyMigrations } from "./migrations.js";

// Load node:sqlite through Node's require so that vitest/vite-node does not
// attempt to transform the static builtin import. At runtime this resolves the
// native module directly.
const require = createRequire(import.meta.url);
const DatabaseSyncCtor: typeof DatabaseSync = require("node:sqlite").DatabaseSync;

/** A thin wrapper around node:sqlite's DatabaseSync with migration tracking. */
export class Database {
  private readonly db: DatabaseSync;

  constructor(db: DatabaseSync) {
    this.db = db;
  }

  /** Open (or create) a SQLite database at the given path, applying migrations. */
  static open(path: string): Database {
    if (path !== ":memory:") {
      const dir = dirname(path);
      if (dir && dir !== ".") mkdirSync(dir, { recursive: true });
    }
    const db = new DatabaseSyncCtor(path);
    db.exec("PRAGMA foreign_keys = ON;");
    const wrapper = new Database(db);
    applyMigrations(wrapper);
    return wrapper;
  }

  /** Open an in-memory database (useful for tests). Migrations still apply. */
  static memory(): Database {
    return Database.open(":memory:");
  }

  get native(): DatabaseSync {
    return this.db;
  }

  exec(sql: string): void {
    this.db.exec(sql);
  }

  prepare(sql: string): import("node:sqlite").StatementSync {
    return this.db.prepare(sql);
  }

  /** Run a function inside a transaction. Rolls back on throw. */
  transaction<T>(fn: () => T): T {
    this.db.exec("BEGIN");
    try {
      const result = fn();
      this.db.exec("COMMIT");
      return result;
    } catch (err) {
      this.db.exec("ROLLBACK");
      throw err;
    }
  }

  close(): void {
    this.db.close();
  }
}
