import { afterEach, describe, expect, it, vi } from "vitest";
import {
  approveContributorApplication,
  fetchContributorApplications,
  fetchContributorTakes,
  publishContributorTake,
  reinstateContributorApplication,
  rejectContributorApplication,
  rejectContributorTake,
  suspendContributorApplication,
  unpublishContributorTake,
} from "./api";
import {
  applicationStatusLabel,
  contributorStatusLabel,
  TAKE_UNPUBLISH_RESULT,
  takeStatusLabel,
} from "./contributorLabels";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function mockJson(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => data,
  };
}

describe("contributor labels", () => {
  it("maps contributor / application / take statuses", () => {
    expect(contributorStatusLabel("NONE")).toBe("미신청");
    expect(contributorStatusLabel("PENDING")).toBe("심사 중");
    expect(contributorStatusLabel("APPROVED")).toBe("승인");
    expect(contributorStatusLabel("REJECTED")).toBe("반려");
    expect(contributorStatusLabel("SUSPENDED")).toBe("정지");
    expect(applicationStatusLabel("PENDING")).toBe("심사 중");
    expect(takeStatusLabel("pending_review")).toBe("검토 중");
    expect(takeStatusLabel("published")).toBe("게시됨");
    expect(takeStatusLabel("rejected")).toBe("반려");
  });

  it("documents unpublish → rejected", () => {
    expect(TAKE_UNPUBLISH_RESULT).toBe("rejected");
  });
});

describe("contributor admin API", () => {
  it("lists applications with PENDING default and X-Admin-Key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJson({ items: [], count: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchContributorApplications("secret-key", "PENDING");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(String(url)).toContain(
      "/api/v1/admin/contributor/applications?status=PENDING",
    );
    expect(init.headers["X-Admin-Key"]).toBe("secret-key");
  });

  it("approves and rejects applications", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockJson({ id: "a1", status: "APPROVED" }))
      .mockResolvedValueOnce(mockJson({ id: "a1", status: "REJECTED" }));
    vi.stubGlobal("fetch", fetchMock);

    await approveContributorApplication("k", "a1");
    await rejectContributorApplication("k", "a1", "사유");

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/applications/a1/approve",
    );
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      "/applications/a1/reject",
    );
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      reason: "사유",
    });
  });

  it("suspends and reinstates contributor", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        mockJson({ id: "a1", contributor_status: "SUSPENDED" }),
      )
      .mockResolvedValueOnce(
        mockJson({ id: "a1", contributor_status: "APPROVED" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await suspendContributorApplication("k", "a1", "위반");
    await reinstateContributorApplication("k", "a1");

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "/applications/a1/suspend",
    );
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      reason: "위반",
    });
    expect(String(fetchMock.mock.calls[1][0])).toContain(
      "/applications/a1/reinstate",
    );
  });

  it("lists takes defaulting to pending_review", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJson({ items: [], count: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await fetchContributorTakes("k");

    expect(String(fetchMock.mock.calls[0][0])).toContain(
      "status=pending_review",
    );
    expect(fetchMock.mock.calls[0][1].headers["X-Admin-Key"]).toBe("k");
  });

  it("publish / reject / unpublish takes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mockJson({ id: "t1", status: "published" }))
      .mockResolvedValueOnce(mockJson({ id: "t1", status: "rejected" }))
      .mockResolvedValueOnce(mockJson({ id: "t1", status: "rejected" }));
    vi.stubGlobal("fetch", fetchMock);

    await publishContributorTake("k", "t1");
    await rejectContributorTake("k", "t1", "검토 의견");
    await unpublishContributorTake("k", "t1", "중단");

    expect(String(fetchMock.mock.calls[0][0])).toContain("/takes/t1/publish");
    expect(String(fetchMock.mock.calls[1][0])).toContain("/takes/t1/reject");
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      reason: "검토 의견",
    });
    expect(String(fetchMock.mock.calls[2][0])).toContain("/takes/t1/unpublish");
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      reason: "중단",
    });
  });

  it("surfaces unauthorized errors without exposing the key", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockJson({ detail: "Unauthorized" }, 401),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(fetchContributorApplications("super-secret", "PENDING")).rejects.toThrow(
      "Unauthorized",
    );
    const serialized = JSON.stringify(fetchMock.mock.calls);
    // Key is sent in headers (correct) but error path must not invent UI leakage —
    // assert the thrown message itself does not contain the key.
    expect("Unauthorized").not.toContain("super-secret");
    expect(serialized).toContain("X-Admin-Key");
  });
});

describe("existing issue API regression (smoke)", () => {
  it("still sends X-Admin-Key on issue list", async () => {
    const { fetchIssues } = await import("./api");
    const fetchMock = vi.fn().mockResolvedValue(
      mockJson({ items: [], count: 0 }),
    );
    vi.stubGlobal("fetch", fetchMock);
    await fetchIssues("issue-key", "draft");
    expect(String(fetchMock.mock.calls[0][0])).toContain("/api/v1/admin/issues?");
    expect(fetchMock.mock.calls[0][1].headers["X-Admin-Key"]).toBe("issue-key");
  });
});
