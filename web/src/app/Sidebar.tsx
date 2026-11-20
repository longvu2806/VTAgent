import { Link } from "@tanstack/react-router";
import { FilesIcon, ListChecksIcon, SquarePenIcon } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ConversationList } from "@/features/conversations/ConversationList";

const NAV = [
  { to: "/", label: "Hội thoại mới", icon: SquarePenIcon, exact: true },
  { to: "/documents", label: "Tài liệu", icon: FilesIcon, exact: false },
  { to: "/rules", label: "Quy tắc rà soát", icon: ListChecksIcon, exact: false },
] as const;

export function Sidebar() {
  return (
    <ScrollArea className="h-full bg-sidebar">
      <div className="flex flex-col gap-5 px-3 py-3">
        <nav className="flex flex-col gap-0.5" aria-label="Chức năng">
          {NAV.map(({ to, label, icon: Icon, exact }) => (
            <Link
              key={to}
              to={to}
              activeOptions={{ exact }}
              className="flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium hover:bg-sidebar-accent data-[status=active]:bg-sidebar-accent"
            >
              <Icon className="size-4" /> {label}
            </Link>
          ))}
        </nav>
        <ConversationList />
      </div>
    </ScrollArea>
  );
}
