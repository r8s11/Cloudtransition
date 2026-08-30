import type { Mission } from "@agentic-os/core";

/** Human-readable single-line summary used by `mission list`. */
export function formatMissionLine(m: Mission): string {
  return `${m.id}\t${m.status}\t${m.title}`;
}

/** Multi-line detail used by `mission show`. */
export function formatMissionDetail(m: Mission): string {
  const lines: string[] = [
    `Mission: ${m.id}`,
    `  Title:       ${m.title}`,
    `  Status:      ${m.status}`,
    `  Priority:    ${m.priority}`,
    `  Created:     ${m.createdAt}`,
    `  Updated:     ${m.updatedAt}`,
  ];
  if (m.description) lines.push(`  Description: ${m.description}`);
  if (m.startedAt) lines.push(`  Started:     ${m.startedAt}`);
  if (m.completedAt) lines.push(`  Completed:   ${m.completedAt}`);
  lines.push(`  Acceptance Criteria:`);
  for (const c of m.acceptanceCriteria) lines.push(`    - ${c}`);
  return lines.join("\n");
}
