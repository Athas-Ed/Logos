import { describe, expect, it } from "vitest";
import { formatByteSize } from "./cacheFormat";

describe("formatByteSize", () => {
  it("formats bytes and KiB/MiB", () => {
    expect(formatByteSize(500)).toBe("500 字节");
    expect(formatByteSize(2048)).toBe("2.0 KiB");
    expect(formatByteSize(5 * 1024 * 1024)).toBe("5.00 MiB");
  });
});
