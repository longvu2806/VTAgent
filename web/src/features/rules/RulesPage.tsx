// Review rules (UC09): filter by genre, switch on or off, add and edit. Rules cannot be
// deleted, so past reviews keep the rule they were measured against (BR18).
import { PencilIcon, PlusIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useRules, useSaveRule } from "@/api/client";
import type { Genre, RuleOut } from "@/api/types";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { SeverityBadge } from "@/features/review/SeverityBadge";
import { conditionText, GENRE } from "@/lib/labels";
import { Choice } from "./Choice";
import { RuleDialog } from "./RuleDialog";

const FILTER = { all: "Mọi thể loại", ...GENRE } as Record<"all" | Genre, string>;

export function RulesPage() {
  const { data: rules, isLoading } = useRules();
  const save = useSaveRule();
  const [genre, setGenre] = useState<"all" | Genre>("all");
  const [editing, setEditing] = useState<RuleOut | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const shown = (rules ?? []).filter((r) => genre === "all" || r.genre === genre);
  const edit = (rule: RuleOut | null) => {
    setEditing(rule);
    setDialogOpen(true);
  };

  return (
    <ScrollArea className="h-full">
      <div className="mx-auto flex max-w-4xl flex-col gap-6 px-8 py-8">
        <header className="flex flex-wrap items-end gap-4">
          <div className="flex flex-1 flex-col gap-1">
            <h1 className="text-2xl font-semibold tracking-tight text-ink">Quy tắc rà soát</h1>
            <p className="max-w-2xl text-muted-foreground">
              Khi rà soát, tài liệu được đối chiếu với các quy tắc đang bật cho thể loại của nó. Quy tắc không xóa được,
              để các lần rà soát cũ vẫn truy được căn cứ; hãy tắt quy tắc khi không dùng nữa.
            </p>
          </div>
          <Button onClick={() => edit(null)}>
            <PlusIcon /> Thêm quy tắc
          </Button>
        </header>
        <Choice label="Lọc theo thể loại" value={genre} options={FILTER} onChange={setGenre} className="w-56" />
        {isLoading ? (
          <Skeleton className="h-40 w-full" />
        ) : shown.length === 0 ? (
          <p className="text-muted-foreground">Chưa có quy tắc nào cho thể loại này.</p>
        ) : (
          <ul className="flex flex-col divide-y border-y">
            {shown.map((r) => (
              <li key={r.id} className="flex items-start gap-4 py-4">
                <div className={`flex flex-1 flex-col gap-1 ${r.enabled ? "" : "opacity-60"}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{r.name}</span>
                    <SeverityBadge severity={r.severity} />
                    <span className="text-xs text-muted-foreground">{GENRE[r.genre]}</span>
                  </div>
                  <p className="text-sm">{conditionText(r.condition)}</p>
                  <p className="text-sm text-muted-foreground">Căn cứ: {r.basis}</p>
                </div>
                <Button variant="ghost" size="icon-sm" aria-label={`Sửa quy tắc ${r.name}`} onClick={() => edit(r)}>
                  <PencilIcon />
                </Button>
                <Switch
                  checked={r.enabled}
                  aria-label={`${r.enabled ? "Tắt" : "Bật"} quy tắc ${r.name}`}
                  onCheckedChange={(enabled) =>
                    save.mutate({ id: r.id, enabled }, { onError: () => toast.error("Không lưu được thay đổi.") })
                  }
                />
              </li>
            ))}
          </ul>
        )}
      </div>
      <RuleDialog open={dialogOpen} rule={editing} onClose={() => setDialogOpen(false)} />
    </ScrollArea>
  );
}
