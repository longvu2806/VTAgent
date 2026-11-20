// Add or edit a review rule. The condition is one of a closed set of deterministic checks
// (SDD §7.8), so the form asks only for the fields that check needs.
import { type FormEvent, useState } from "react";
import { toast } from "sonner";
import { useSaveRule } from "@/api/client";
import type { Genre, RuleCondition, RuleOut, Severity } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { CONDITION, GENRE, SEVERITY } from "@/lib/labels";
import { Choice } from "./Choice";

type ConditionType = RuleCondition["type"];

interface Draft {
  name: string;
  genre: Genre;
  severity: Severity;
  basis: string;
  enabled: boolean;
  type: ConditionType;
  patterns: string; // comma separated
  field: string;
  near: string;
  max: string;
  table_pattern: string;
}

const UNIT: Partial<Record<ConditionType, string>> = { max_percent: "%", max_amount: "đồng", max_days: "ngày" };

function toDraft(rule: RuleOut | null): Draft {
  const blank: Draft = {
    name: "", genre: "contract", severity: "medium", basis: "", enabled: true, type: "missing_clause",
    patterns: "", field: "", near: "", max: "", table_pattern: "",
  };
  if (!rule) return blank;
  const c = rule.condition;
  return {
    ...blank, name: rule.name, genre: rule.genre, severity: rule.severity, basis: rule.basis, enabled: rule.enabled,
    type: c.type,
    patterns: c.type === "missing_clause" ? c.patterns.join(", ") : "",
    field: c.type === "required_metadata" ? c.field : "",
    near: "near" in c ? c.near : "",
    max: "max" in c ? String(c.max) : "",
    table_pattern: c.type === "sum_mismatch" ? c.table_pattern : "",
  };
}

/** The condition the draft describes, or what is missing from it. */
function toCondition(d: Draft): RuleCondition | string {
  switch (d.type) {
    case "missing_clause": {
      const patterns = d.patterns.split(",").map((p) => p.trim()).filter(Boolean);
      return patterns.length ? { type: d.type, patterns } : "Nhập ít nhất một cụm từ nhận diện điều khoản.";
    }
    case "required_metadata":
      return d.field.trim() ? { type: d.type, field: d.field.trim() } : "Nhập tên trường bắt buộc.";
    case "sum_mismatch":
      return d.table_pattern.trim() ? { type: d.type, table_pattern: d.table_pattern.trim() } : "Nhập mẫu tên bảng.";
    default: {
      const max = Number(d.max.replace(",", "."));
      if (!d.near.trim()) return "Nhập cụm từ đứng gần giá trị cần kiểm tra.";
      return max > 0 ? { type: d.type, near: d.near.trim(), max } : "Mức tối đa phải là số lớn hơn 0.";
    }
  }
}

interface Props {
  open: boolean;
  rule: RuleOut | null; // null adds a new rule
  onClose: () => void;
}

export function RuleDialog({ open, rule, onClose }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{rule ? "Sửa quy tắc" : "Thêm quy tắc rà soát"}</DialogTitle>
        </DialogHeader>
        {/* Remount per rule so the form starts from the rule being edited. */}
        {open && <RuleForm key={rule?.id ?? "new"} rule={rule} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  );
}

function RuleForm({ rule, onDone }: { rule: RuleOut | null; onDone: () => void }) {
  const [d, setDraft] = useState(() => toDraft(rule));
  const [problem, setProblem] = useState<string | null>(null);
  const save = useSaveRule();
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((prev) => ({ ...prev, [key]: value }));

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const condition = toCondition(d);
    const missing = !d.name.trim() ? "Nhập tên quy tắc." : !d.basis.trim() ? "Nhập căn cứ của quy tắc." : null;
    if (missing || typeof condition === "string") return setProblem(missing ?? (condition as string));
    save.mutate(
      {
        id: rule?.id, name: d.name.trim(), genre: d.genre, severity: d.severity, basis: d.basis.trim(),
        enabled: d.enabled, condition,
      },
      {
        onSuccess: () => {
          toast.success(rule ? "Đã lưu quy tắc" : "Đã thêm quy tắc");
          onDone();
        },
        onError: (err) => setProblem(err.message),
      },
    );
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="rule-name">Tên quy tắc</Label>
        <Input id="rule-name" value={d.name} onChange={(e) => set("name", e.target.value)} autoFocus />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-genre">Áp dụng cho</Label>
          <Choice id="rule-genre" value={d.genre} options={GENRE} onChange={(v) => set("genre", v)} />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-severity">Mức độ</Label>
          <Choice id="rule-severity" value={d.severity} options={SEVERITY} onChange={(v) => set("severity", v)} />
        </div>
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="rule-type">Điều kiện</Label>
        <Choice id="rule-type" value={d.type} options={CONDITION} onChange={(v) => set("type", v)} />
      </div>
      {d.type === "missing_clause" && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-patterns">Cụm từ nhận diện điều khoản, cách nhau bằng dấu phẩy</Label>
          <Input id="rule-patterns" value={d.patterns} onChange={(e) => set("patterns", e.target.value)} placeholder="giải quyết tranh chấp, trọng tài" />
        </div>
      )}
      {d.type === "required_metadata" && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-field">Trường bắt buộc</Label>
          <Input id="rule-field" value={d.field} onChange={(e) => set("field", e.target.value)} placeholder="effective_date" />
        </div>
      )}
      {d.type === "sum_mismatch" && (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="rule-table">Mẫu tên bảng</Label>
          <Input id="rule-table" value={d.table_pattern} onChange={(e) => set("table_pattern", e.target.value)} placeholder="Bảng tổng hợp" />
        </div>
      )}
      {UNIT[d.type] && (
        <div className="grid grid-cols-[1fr_10rem] gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rule-near">Gần cụm từ</Label>
            <Input id="rule-near" value={d.near} onChange={(e) => set("near", e.target.value)} placeholder="phạt vi phạm" />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="rule-max">Tối đa ({UNIT[d.type]})</Label>
            <Input id="rule-max" inputMode="decimal" value={d.max} onChange={(e) => set("max", e.target.value)} />
          </div>
        </div>
      )}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="rule-basis">Căn cứ</Label>
        <Textarea id="rule-basis" value={d.basis} onChange={(e) => set("basis", e.target.value)} rows={2} placeholder="Điều, khoản hoặc chính sách mà quy tắc dựa vào" />
      </div>
      <Label className="flex items-center gap-2.5 font-normal">
        <Switch checked={d.enabled} onCheckedChange={(v) => set("enabled", v)} /> Bật quy tắc
      </Label>
      {problem && (
        <p role="alert" className="text-sm text-destructive">
          {problem}
        </p>
      )}
      <DialogFooter>
        <Button type="button" variant="outline" onClick={onDone}>
          Hủy
        </Button>
        <Button type="submit" disabled={save.isPending}>
          {rule ? "Lưu" : "Thêm quy tắc"}
        </Button>
      </DialogFooter>
    </form>
  );
}
