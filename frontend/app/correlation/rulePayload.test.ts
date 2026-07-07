import { describe, it, expect } from "vitest";

import {
  ANY_REGION,
  DEFAULT_GROUP_BY,
  buildScope,
  parseGroupBy,
} from "./rulePayload";

describe("buildScope", () => {
  it("includes source and region when both are set", () => {
    expect(buildScope({ source: "Prometheus", region: "us-east-1" })).toEqual({
      source: "Prometheus",
      region: "us-east-1",
    });
  });

  it("omits region when it is ANY_REGION (broad match)", () => {
    expect(buildScope({ source: "Prometheus", region: ANY_REGION })).toEqual({
      source: "Prometheus",
    });
  });

  it("omits region when it is empty", () => {
    expect(buildScope({ source: "Grafana", region: "" })).toEqual({
      source: "Grafana",
    });
  });

  it("never emits array scope keys (which the engine cannot resolve)", () => {
    const scope = buildScope({ source: "Prometheus", region: "us-east-1" });
    for (const value of Object.values(scope)) {
      expect(Array.isArray(value)).toBe(false);
    }
  });

  it("returns an empty (match-all) scope when nothing is constrained", () => {
    expect(buildScope({ region: ANY_REGION })).toEqual({});
  });
});

describe("parseGroupBy", () => {
  it("splits, trims and de-duplicates comma-separated fields", () => {
    expect(parseGroupBy(" service , host ,service")).toEqual(["service", "host"]);
  });

  it("falls back to the default when input is empty or blank", () => {
    expect(parseGroupBy("")).toEqual(DEFAULT_GROUP_BY);
    expect(parseGroupBy("  ,  ")).toEqual(DEFAULT_GROUP_BY);
  });

  it("always returns at least one field (API requires min_length 1)", () => {
    expect(parseGroupBy("").length).toBeGreaterThan(0);
  });
});
