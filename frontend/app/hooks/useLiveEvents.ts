'use client';

/**
 * Live-update subscription over the backend's SSE stream.
 *
 * The backend publishes thin invalidation events (`{"type": "alert.created",
 * "id": "..."}`) on `GET /events/stream`. This hook holds one long-lived
 * connection and invokes the caller's refetch callback whenever an event
 * matching the given type prefixes arrives.
 *
 * The native `EventSource` API cannot send an `Authorization` header, so the
 * stream is consumed with `fetch` + a streaming reader, injecting the same
 * bearer token `apiFetch` uses. Reconnects automatically with backoff.
 */

import { useEffect, useRef } from 'react';
import { API_BASE_URL, getToken } from '../services/apiClient';

export interface LiveEvent {
  type: string;
  id?: string;
}

/**
 * Pull complete SSE `data:` payloads out of a text buffer.
 *
 * Frames are separated by a blank line; the trailing partial frame (if any)
 * is returned as `rest` so the caller can prepend it to the next chunk.
 * Comment lines (`: keep-alive`) are ignored.
 */
export function extractSseData(buffer: string): { payloads: string[]; rest: string } {
  const frames = buffer.split(/\r?\n\r?\n/);
  const rest = frames.pop() ?? '';
  const payloads: string[] = [];
  for (const frame of frames) {
    const dataLines = frame
      .split(/\r?\n/)
      .filter(line => line.startsWith('data:'))
      .map(line => line.slice('data:'.length).trimStart());
    if (dataLines.length > 0) payloads.push(dataLines.join('\n'));
  }
  return { payloads, rest };
}

const INITIAL_RETRY_MS = 3_000;
const MAX_RETRY_MS = 30_000;

/**
 * Subscribe to live mutation events and trigger a refetch when one matches.
 *
 * @param typePrefixes event-type prefixes this consumer cares about,
 *   e.g. `['alert.', 'aggregate.']`
 * @param onInvalidate refetch callback; called at most once per
 *   `throttleMs` window (leading + trailing) so alert storms coalesce
 *   into a bounded number of refetches
 */
export function useLiveEvents(
  typePrefixes: string[],
  onInvalidate: () => void,
  throttleMs: number = 1_000,
): void {
  const onInvalidateRef = useRef(onInvalidate);
  onInvalidateRef.current = onInvalidate;
  const prefixesRef = useRef(typePrefixes);
  prefixesRef.current = typePrefixes;

  useEffect(() => {
    const controller = new AbortController();
    let stopped = false;
    let retryMs = INITIAL_RETRY_MS;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    let cooldownTimer: ReturnType<typeof setTimeout> | null = null;
    let pendingInvalidate = false;

    const fireInvalidate = () => {
      if (cooldownTimer !== null) {
        pendingInvalidate = true;
        return;
      }
      onInvalidateRef.current();
      cooldownTimer = setTimeout(() => {
        cooldownTimer = null;
        if (pendingInvalidate) {
          pendingInvalidate = false;
          fireInvalidate();
        }
      }, throttleMs);
    };

    const handlePayload = (payload: string) => {
      let event: LiveEvent;
      try {
        event = JSON.parse(payload) as LiveEvent;
      } catch {
        return;
      }
      if (typeof event?.type !== 'string') return;
      if (prefixesRef.current.some(prefix => event.type.startsWith(prefix))) {
        fireInvalidate();
      }
    };

    const connect = async () => {
      const token = getToken();
      if (!token || stopped) return;

      try {
        const response = await fetch(`${API_BASE_URL}/events/stream`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (response.status === 401) return; // session expired — stop retrying
        if (!response.ok || !response.body) throw new Error(`SSE ${response.status}`);

        retryMs = INITIAL_RETRY_MS; // connected — reset backoff
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const { payloads, rest } = extractSseData(buffer);
          buffer = rest;
          payloads.forEach(handlePayload);
        }
      } catch {
        // Network error / server restart — fall through to reconnect.
      }

      if (!stopped) {
        retryTimer = setTimeout(connect, retryMs);
        retryMs = Math.min(retryMs * 2, MAX_RETRY_MS);
      }
    };

    connect();

    return () => {
      stopped = true;
      controller.abort();
      if (retryTimer !== null) clearTimeout(retryTimer);
      if (cooldownTimer !== null) clearTimeout(cooldownTimer);
    };
  }, [throttleMs]);
}
