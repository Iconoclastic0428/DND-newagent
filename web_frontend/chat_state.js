export const CHAT_VISIBLE_LIMIT = 28;
export const CHAT_RECENT_KEEP_COUNT = 18;
export const LOCAL_CHAT_LIMIT = 30;

const CHAT_FINGERPRINT_SEPARATOR = '\u001e';

export function createChatFeedState() {
  return {
    localEntries: [],
    authoritativeFingerprint: authoritativeChatFingerprint([]),
    authoritativeGeneration: 0,
  };
}

export function chatEntrySignature(entry) {
  return `${entry.speaker}::${entry.text}::${entry.category}`;
}

function authoritativeChatFingerprint(entries) {
  return entries.map(entry => `${entry.entry_id || ''}::${chatEntrySignature(entry)}`).join(CHAT_FINGERPRINT_SEPARATOR);
}

function localEntryGeneration(entry) {
  return Number.isInteger(entry.authoritative_generation) ? entry.authoritative_generation : 0;
}

export function noteAuthoritativeChat(chatFeed, authoritativeEntries) {
  const nextFingerprint = authoritativeChatFingerprint(authoritativeEntries || []);
  if (nextFingerprint === chatFeed.authoritativeFingerprint) {
    return;
  }
  chatFeed.authoritativeFingerprint = nextFingerprint;
  chatFeed.authoritativeGeneration += 1;
  chatFeed.localEntries = chatFeed.localEntries.filter(entry => (
    entry.category !== 'thinking' || localEntryGeneration(entry) >= chatFeed.authoritativeGeneration
  ));
}

export function appendLocalChatEntry(chatFeed, entry, nowMillis = Date.now()) {
  const localEntry = {
    entry_id: entry.entry_id || `local:${nowMillis}:${chatFeed.localEntries.length}`,
    speaker: entry.speaker || 'System',
    text: entry.text,
    category: entry.category || 'system',
    visibility: entry.visibility || 'public',
    authoritative_generation: chatFeed.authoritativeGeneration,
  };
  chatFeed.localEntries.push(localEntry);
  chatFeed.localEntries = chatFeed.localEntries.slice(-LOCAL_CHAT_LIMIT);
  return localEntry;
}

function trimSummaryText(text) {
  const normalized = String(text || '').replace(/\s+/g, ' ').trim();
  if (!normalized) return '';
  return normalized.length > 120 ? `${normalized.slice(0, 117)}...` : normalized;
}

function buildChatSummaryEntry(entries) {
  const speakers = [...new Set(entries.map(entry => entry.speaker).filter(Boolean))].slice(0, 5);
  const highlightCandidates = [];
  if (entries.length) {
    highlightCandidates.push(entries[0]);
    const checkEntry = entries.find(entry => entry.category === 'check');
    if (checkEntry) highlightCandidates.push(checkEntry);
    const playerEntry = entries.find(entry => entry.category === 'player');
    if (playerEntry) highlightCandidates.push(playerEntry);
    const recentTail = entries.slice(-2);
    highlightCandidates.push(...recentTail);
  }
  const highlights = [];
  const seen = new Set();
  for (const entry of highlightCandidates) {
    if (!entry) continue;
    const trimmed = trimSummaryText(entry.text);
    if (!trimmed || seen.has(trimmed)) continue;
    highlights.push(trimmed);
    seen.add(trimmed);
    if (highlights.length >= 4) break;
  }
  const speakerText = speakers.length ? ` Speakers: ${speakers.join(', ')}.` : '';
  const highlightText = highlights.length ? ` Highlights: ${highlights.join(' / ')}` : '';
  return {
    entry_id: `summary:${entries.length}`,
    speaker: 'Summary',
    text: `Earlier chat summary (${entries.length} entries hidden).${speakerText}${highlightText}`.trim(),
    category: 'summary',
    visibility: 'public',
  };
}

export function buildVisibleChatEntries(entries) {
  if (entries.length <= CHAT_VISIBLE_LIMIT) {
    return entries;
  }
  const splitIndex = Math.max(entries.length - CHAT_RECENT_KEEP_COUNT, 1);
  const older = entries.slice(0, splitIndex);
  const recent = entries.slice(splitIndex);
  return [buildChatSummaryEntry(older), ...recent];
}

export function buildChatRenderEntries(chatFeed, authoritativeEntries) {
  const authoritativeSignatures = new Set(authoritativeEntries.map(chatEntrySignature));
  const localEntries = chatFeed.localEntries.filter(entry => !authoritativeSignatures.has(chatEntrySignature(entry)));
  return buildVisibleChatEntries([...authoritativeEntries, ...localEntries]);
}
