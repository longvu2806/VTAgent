import type { ReactNode } from "react";

/** The reading column with the composer pinned under it, and the disclaimer (FR-32). */
export function ChatFrame({ children, composer }: { children: ReactNode; composer: ReactNode }) {
  return (
    <div className="flex h-full flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto w-full max-w-[46rem] px-6">{children}</div>
      </div>
      <div className="mx-auto w-full max-w-[46rem] px-6 pb-3">
        {composer}
        <p className="mt-2 text-center text-xs text-muted-foreground">
          VTAgent chỉ trả lời từ tài liệu đã nạp và không thay thế tư vấn chuyên môn.
        </p>
      </div>
    </div>
  );
}
