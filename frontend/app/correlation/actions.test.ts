import { describe, it, expect } from "vitest";

import {
  ACTION_OPTIONS,
  DEFAULT_ACTIONS,
  toggleAction,
  type CorrelationActionId,
} from "./actions";

describe("correlation action options", () => {
  it("offers both aggregate and email in the multiselect", () => {
    const ids = ACTION_OPTIONS.map((o) => o.id);
    expect(ids).toContain("aggregate");
    expect(ids).toContain("email");
  });

  it("defaults to aggregate only", () => {
    expect(DEFAULT_ACTIONS).toEqual(["aggregate"]);
  });
});

describe("toggleAction", () => {
  it("adds an action when it is not selected", () => {
    expect(toggleAction(["aggregate"], "email")).toEqual(["aggregate", "email"]);
  });

  it("removes an action when it is already selected", () => {
    expect(toggleAction(["aggregate", "email"], "email")).toEqual(["aggregate"]);
  });

  it("keeps at least one action selected (removing the last is a no-op)", () => {
    expect(toggleAction(["email"], "email")).toEqual(["email"]);
  });

  it("returns actions in canonical order regardless of toggle order", () => {
    // Select email first, then aggregate — result should still be aggregate, email.
    const afterEmail = toggleAction(["email"] as CorrelationActionId[], "email");
    expect(afterEmail).toEqual(["email"]); // no-op (last one)

    const built = toggleAction(["email"], "aggregate");
    expect(built).toEqual(["aggregate", "email"]);
  });

  it("does not mutate the input array", () => {
    const input: CorrelationActionId[] = ["aggregate"];
    toggleAction(input, "email");
    expect(input).toEqual(["aggregate"]);
  });
});
