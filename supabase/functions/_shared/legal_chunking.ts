export type SemanticChunk = {
  content: string;
  section: string | null;
  sourceStart: number;
  sourceEnd: number;
};

type SourcePart = Omit<SemanticChunk, "section">;

const NAMED_HEADING = /^(?:раздел|глава|параграф|§|статья|часть|пункт|подпункт|chapter|section|article|part)\s+(?:[IVXLCDM]+|\d+(?:\.\d+)*)(?:\s*[.:-]\s*|\s+).+/iu;
const ALL_CAPS = /^[А-ЯЁA-Z][А-ЯЁA-Z\s\-–—]{3,}:?$/u;
const DECISION = /^(?:ПОСТАНОВИЛ|ОПРЕДЕЛИЛ|ПРИГОВОРИЛ|УСТАНОВИЛ|ПРОШУ|ХОДАТАЙСТВО|ВОЗРАЖЕНИЯ)\s*:?$/u;
const TABLE_SEPARATOR = /^\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?$/u;

function canonicalHeading(value: string): string {
  const stripped = value.trim();
  const compact = stripped.replace(/\s+/gu, "").replace(/:$/u, "");
  if (["УСТАНОВИЛ", "ПОСТАНОВИЛ", "ОПРЕДЕЛИЛ", "ПРИГОВОРИЛ"].includes(compact)) return compact;
  return stripped.replace(/^#+\s*/u, "").replace(/:$/u, "").trim();
}

function isHeading(value: string): boolean {
  const stripped = value.trim();
  return stripped.length > 0 && stripped.length <= 160 && (
    stripped.startsWith("#") || ALL_CAPS.test(stripped) || DECISION.test(canonicalHeading(stripped)) || NAMED_HEADING.test(stripped)
  );
}

function isTable(lines: string[]): boolean {
  return lines.length >= 2 && lines[0].includes("|") && TABLE_SEPARATOR.test(lines[1].trim());
}

function trimSpan(value: string, start: number, end: number): [number, number] {
  while (start < end && /\s/u.test(value[start])) start += 1;
  while (end > start && /\s/u.test(value[end - 1])) end -= 1;
  return [start, end];
}

function hardSplitSpans(value: string, start: number, end: number, maxChars: number): Array<[number, number]> {
  const spans: Array<[number, number]> = [];
  while (end - start > maxChars) {
    let splitAt = value.lastIndexOf(" ", start + maxChars);
    if (splitAt <= start) splitAt = value.indexOf(" ", start + maxChars);
    if (splitAt <= start || splitAt >= end) return [...spans, [start, end]];
    spans.push(trimSpan(value, start, splitAt));
    [start, end] = trimSpan(value, splitAt, end);
  }
  return start < end ? [...spans, [start, end]] : spans;
}

function splitOversized(value: string, maxChars: number, table: boolean): SourcePart[] {
  if (value.length <= maxChars) return [{ content: value, sourceStart: 0, sourceEnd: value.length }];
  if (table) {
    const lines = value.split("\n");
    const header = isTable(lines) ? lines.slice(0, 2) : [];
    const rows = header.length ? lines.slice(2) : lines;
    const headerText = header.join("\n");
    const chunks: SourcePart[] = [];
    let cursor = headerText.length + (headerText ? 1 : 0);
    let rowStart = cursor;
    let current = "";
    for (const row of rows) {
      const candidate = current ? `${current}\n${row}` : row;
      if (`${headerText}${headerText ? "\n" : ""}${candidate}`.length > maxChars && current) {
        chunks.push({
          content: `${headerText}${headerText ? "\n" : ""}${current}`,
          sourceStart: rowStart,
          sourceEnd: cursor - 1,
        });
        rowStart = cursor;
        current = row;
      } else current = candidate;
      cursor += row.length + 1;
    }
    return current
      ? [...chunks, { content: `${headerText}${headerText ? "\n" : ""}${current}`, sourceStart: rowStart, sourceEnd: cursor - 1 }]
      : chunks;
  }
  const boundaries = [0, ...Array.from(value.matchAll(/(?<=[!?;])\s+|(?<=\.)\s+(?=[А-ЯЁA-Z])/gu), (match) => match.index + match[0].length), value.length];
  const chunks: Array<[number, number]> = [];
  let currentStart: number | null = null;
  let currentEnd: number | null = null;
  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const [start, end] = trimSpan(value, boundaries[index], boundaries[index + 1]);
    if (start >= end) continue;
    if (currentStart === null || end - currentStart <= maxChars) {
      currentStart = currentStart === null ? start : currentStart;
      currentEnd = end;
    } else {
      if (currentEnd !== null) chunks.push([currentStart, currentEnd]);
      if (end - start <= maxChars) {
        currentStart = start;
        currentEnd = end;
      } else {
        chunks.push(...hardSplitSpans(value, start, end, maxChars));
        currentStart = null;
        currentEnd = null;
      }
    }
  }
  if (currentStart !== null && currentEnd !== null) chunks.push([currentStart, currentEnd]);
  return chunks.map(([sourceStart, sourceEnd]) => ({ content: value.slice(sourceStart, sourceEnd), sourceStart, sourceEnd }));
}

export function semanticLegalChunks(text: string, targetChars = 2600, maxChars = 3400): SemanticChunk[] {
  if (!(targetChars > 0 && targetChars <= maxChars)) throw new Error("invalid_chunk_limits");
  const normalized = text.replace(/\r\n/gu, "\n").trim();
  if (!normalized) return [];
  const chunks: SemanticChunk[] = [];
  let section: string | null = null;
  let current: SemanticChunk[] = [];
  const flush = () => {
    if (!current.length) return;
    chunks.push({
      content: current.map((item) => item.content).join("\n\n"),
      section,
      sourceStart: current[0].sourceStart,
      sourceEnd: current[current.length - 1].sourceEnd,
    });
    current = [];
  };
  let cursor = 0;
  for (const rawBlock of normalized.split(/\n\s*\n/gu)) {
    const block = rawBlock.trim();
    if (!block) continue;
    const start = normalized.indexOf(block, cursor);
    const end = start + block.length;
    cursor = end;
    if (isHeading(block)) {
      flush();
      section = canonicalHeading(block);
    }
    const lines = block.split("\n");
    for (const part of splitOversized(block, maxChars, isTable(lines))) {
      const sourceStart = start + part.sourceStart;
      const sourceEnd = start + part.sourceEnd;
      const candidateLength = [...current.map((item) => item.content), part.content].join("\n\n").length;
      if (current.length && candidateLength > maxChars) flush();
      current.push({ content: part.content, section, sourceStart, sourceEnd });
      if (candidateLength >= targetChars && !isTable(lines)) flush();
    }
  }
  flush();
  return chunks;
}
