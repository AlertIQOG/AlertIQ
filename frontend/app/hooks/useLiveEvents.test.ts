import { describe, expect, it } from 'vitest';
import { extractSseData } from './useLiveEvents';

describe('extractSseData', () => {
  it('extracts a complete data frame', () => {
    const { payloads, rest } = extractSseData('data: {"type":"alert.created"}\n\n');
    expect(payloads).toEqual(['{"type":"alert.created"}']);
    expect(rest).toBe('');
  });

  it('keeps a partial frame as remainder for the next chunk', () => {
    const { payloads, rest } = extractSseData('data: {"type":"a');
    expect(payloads).toEqual([]);
    expect(rest).toBe('data: {"type":"a');
  });

  it('extracts multiple frames from one chunk', () => {
    const chunk = 'data: one\n\ndata: two\n\ndata: thr';
    const { payloads, rest } = extractSseData(chunk);
    expect(payloads).toEqual(['one', 'two']);
    expect(rest).toBe('data: thr');
  });

  it('ignores comment-only frames (keep-alives)', () => {
    const { payloads, rest } = extractSseData(': connected\n\n: keep-alive\n\ndata: x\n\n');
    expect(payloads).toEqual(['x']);
    expect(rest).toBe('');
  });

  it('handles CRLF line endings', () => {
    const { payloads } = extractSseData('data: hello\r\n\r\n');
    expect(payloads).toEqual(['hello']);
  });

  it('joins multi-line data fields with newlines', () => {
    const { payloads } = extractSseData('data: line1\ndata: line2\n\n');
    expect(payloads).toEqual(['line1\nline2']);
  });
});
