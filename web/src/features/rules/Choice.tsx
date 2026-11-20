import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface Props<T extends string> {
  id?: string;
  label?: string;
  value: T;
  options: Record<T, string>;
  onChange: (value: T) => void;
  className?: string;
}

/** A select over a fixed set of labelled values. */
export function Choice<T extends string>({ id, label, value, options, onChange, className = "w-full" }: Props<T>) {
  return (
    <Select value={value} items={options} onValueChange={(v) => onChange(v as T)}>
      <SelectTrigger id={id} aria-label={label} className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {(Object.entries(options) as [T, string][]).map(([v, text]) => (
          <SelectItem key={v} value={v}>
            {text}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
