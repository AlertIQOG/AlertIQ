import { describe, it, expect } from "vitest";

import {
  ANY_REGION,
  ANY_SOURCE,
  CUSTOM_TIME_WINDOW,
  DEFAULT_GROUP_BY,
  OPERATOR_LABELS,
  SOURCE_OPTIONS,
  TIME_WINDOW_PRESETS,
  buildScope,
  mapOperator,
  mapOperatorToLabel,
  minutesToTimeWindow,
  parseGroupBy,
  parseRecipients,
  timeWindowToMinutes,
  validateEmailRecipients,
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

  it("omits source when it is ANY_SOURCE", () => {
    expect(buildScope({ source: ANY_SOURCE, region: "us-east-1" })).toEqual({
      region: "us-east-1",
    });
  });

  it("offers Any as a source option so a rule need not name a provider", () => {
    expect(SOURCE_OPTIONS).toContain(ANY_SOURCE);
  });

  // The engine requires EVERY scope key to resolve on the alert, so a key it
  // cannot resolve makes the rule permanently unmatchable. The edit page used
  // to hand-build `environment` / `sources` / `environments` and broke every
  // rule it saved.
  it("never emits keys the engine cannot resolve", () => {
    const scope = buildScope({ source: "Grafana", region: "us-east-1" });
    expect(Object.keys(scope).sort()).toEqual(["region", "source"]);
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

describe("parseRecipients", () => {
  it("splits, trims and de-duplicates comma-separated emails", () => {
    expect(parseRecipients(" a@x.com , b@y.com ,a@x.com")).toEqual([
      "a@x.com",
      "b@y.com",
    ]);
  });

  it("returns an empty array for blank input", () => {
    expect(parseRecipients("")).toEqual([]);
    expect(parseRecipients("  ,  ")).toEqual([]);
  });
});

// Both the create and edit forms read these, so a drift here is what let the
// two pages disagree about what a rule means.
describe("operators", () => {
  it("maps every offered label to an API operator and back", () => {
    for (const label of OPERATOR_LABELS) {
      expect(mapOperatorToLabel(mapOperator(label))).toBe(label);
    }
  });

  it("maps unknown input to equals / Equals rather than throwing", () => {
    expect(mapOperator("nonsense")).toBe("equals");
    expect(mapOperatorToLabel("nonsense")).toBe("Equals");
  });

  it("covers the operators the backend accepts", () => {
    expect(OPERATOR_LABELS.map(mapOperator).sort()).toEqual(
      [
        "contains",
        "equals",
        "greater_or_equal",
        "greater_than",
        "is_present",
        "less_or_equal",
        "less_than",
        "not_equals",
      ].sort(),
    );
  });
});

describe("time window", () => {
  it("round-trips every preset", () => {
    for (const preset of TIME_WINDOW_PRESETS) {
      expect(timeWindowToMinutes(minutesToTimeWindow(preset.minutes))).toBe(
        preset.minutes,
      );
      expect(minutesToTimeWindow(preset.minutes).window).toBe(preset.label);
    }
  });

  it("reads 1 Hour as 60 minutes, not 1", () => {
    expect(
      timeWindowToMinutes({
        window: "1 Hour",
        customValue: "",
        customUnit: "Minutes",
      }),
    ).toBe(60);
  });

  it("falls back to the custom input for a non-preset value", () => {
    const state = minutesToTimeWindow(45);
    expect(state.window).toBe(CUSTOM_TIME_WINDOW);
    expect(state.customValue).toBe("45");
    expect(timeWindowToMinutes(state)).toBe(45);
  });

  it("converts each custom unit to minutes", () => {
    const cases: Array<[string, string, number]> = [
      ["90", "Seconds", 2], // rounds up: a window must not be zero
      ["45", "Minutes", 45],
      ["2", "Hours", 120],
      ["1", "Days", 1440],
    ];
    for (const [customValue, customUnit, expected] of cases) {
      expect(
        timeWindowToMinutes({
          window: CUSTOM_TIME_WINDOW,
          customValue,
          customUnit,
        }),
      ).toBe(expected);
    }
  });
});

describe("validateEmailRecipients", () => {
  it("passes when the email action is not selected (recipients ignored)", () => {
    expect(validateEmailRecipients(["aggregate"], []).ok).toBe(true);
  });

  it("fails when email is selected but there are no recipients", () => {
    const result = validateEmailRecipients(["aggregate", "email"], []);
    expect(result.ok).toBe(false);
    expect(result.error).toBeTruthy();
  });

  it("fails when any recipient is not a valid email", () => {
    expect(validateEmailRecipients(["email"], ["a@x.com", "nope"]).ok).toBe(false);
  });

  it("passes when email is selected with valid recipients", () => {
    expect(validateEmailRecipients(["email"], ["a@x.com", "b@y.com"]).ok).toBe(true);
  });
});
