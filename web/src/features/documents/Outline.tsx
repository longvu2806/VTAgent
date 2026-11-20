// The structure the ingest recognised (FR-04): chapters, articles and headings with pages.
import { useOutline } from "@/api/client";
import type { OutlineNode } from "@/api/types";
import { Skeleton } from "@/components/ui/skeleton";
import { outlineLabel, outlineUnit } from "@/lib/labels";

export function Outline({ documentId }: { documentId: string }) {
  const { data: root, isLoading } = useOutline(documentId);
  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (!root?.children.length) return <p className="text-muted-foreground">Chưa nhận diện được cấu trúc của tài liệu này.</p>;
  return <Tree nodes={root.children} nested={false} />;
}

function Tree({ nodes, nested }: { nodes: OutlineNode[]; nested: boolean }) {
  return (
    <ul className={nested ? "ml-2 border-l pl-4" : undefined}>
      {nodes.map((n) => {
        // Untitled clauses or points are summarised as a count rather than listed.
        const counted = n.children.length > 0 && n.children.every((c) => !c.title && !c.children.length);
        return (
          <li key={n.id}>
            <div className="flex items-baseline gap-3 py-1.5">
              <span className={n.level === "chapter" || n.level === "part" ? "font-semibold" : undefined}>
                {outlineLabel(n)}
              </span>
              {counted && (
                <span className="text-xs text-muted-foreground">
                  {n.children.length} {outlineUnit(n.children[0].level)}
                </span>
              )}
              {n.page !== null && <span className="ml-auto text-xs text-muted-foreground tabular-nums">tr. {n.page}</span>}
            </div>
            {!counted && n.children.length > 0 && <Tree nodes={n.children} nested />}
          </li>
        );
      })}
    </ul>
  );
}
