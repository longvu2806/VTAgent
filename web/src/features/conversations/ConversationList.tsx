// Conversation history in the sidebar: pinned first, then recent, each with a menu to
// pin, rename or delete it.
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { EllipsisIcon, PencilIcon, PinIcon, PinOffIcon, Trash2Icon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useConversations, useDeleteConversation, useUpdateConversation } from "@/api/client";
import type { ConversationOut } from "@/api/types";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { forgetChat } from "@/features/chat/chats";
import { useUi } from "@/stores/ui";

const titleOf = (c: ConversationOut) => c.title ?? "Hội thoại chưa đặt tên";

export function ConversationList() {
  const { data: conversations = [] } = useConversations();
  const pinned = conversations.filter((c) => c.pinned);
  const recent = conversations.filter((c) => !c.pinned);
  return (
    <div className="flex flex-col gap-5">
      {pinned.length > 0 && <Section title="Đã ghim" items={pinned} />}
      <Section title="Gần đây" items={recent} empty="Chưa có hội thoại nào." />
    </div>
  );
}

function Section({ title, items, empty }: { title: string; items: ConversationOut[]; empty?: string }) {
  return (
    <section className="flex flex-col gap-0.5" aria-label={title}>
      <h2 className="px-2.5 pb-1 text-xs font-medium text-muted-foreground">{title}</h2>
      {items.length === 0 && empty && <p className="px-2.5 text-sm text-muted-foreground">{empty}</p>}
      <ul className="flex flex-col gap-0.5">
        {items.map((c) => (
          <ConversationItem key={c.id} conversation={c} />
        ))}
      </ul>
    </section>
  );
}

function ConversationItem({ conversation: c }: { conversation: ConversationOut }) {
  const [confirming, setConfirming] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const update = useUpdateConversation();
  const remove = useDeleteConversation();
  const navigate = useNavigate();
  const { conversationId } = useParams({ strict: false });
  const title = titleOf(c);

  const deleteConversation = () =>
    remove.mutate(c.id, {
      onSuccess: () => {
        setConfirming(false);
        forgetChat(c.id);
        if (conversationId === c.id) {
          useUi.getState().closeSource();
          navigate({ to: "/" });
        }
        toast.success("Đã xóa hội thoại");
      },
      onError: () => toast.error("Không xóa được hội thoại. Thử lại."),
    });

  const rename = (value: string) => {
    setRenaming(false);
    const next = value.trim();
    if (next && next !== c.title) update.mutate({ id: c.id, title: next });
  };

  if (renaming) {
    return (
      <li>
        <input
          autoFocus
          defaultValue={title}
          aria-label="Tên mới của hội thoại"
          onFocus={(e) => e.currentTarget.select()}
          onBlur={(e) => rename(e.currentTarget.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") rename(e.currentTarget.value);
            if (e.key === "Escape") setRenaming(false);
          }}
          className="w-full rounded-md border border-ring bg-background px-2.5 py-1.5 text-sm outline-none"
        />
      </li>
    );
  }

  return (
    <li className="group/item relative">
      <Link
        to="/c/$conversationId"
        params={{ conversationId: c.id }}
        className="block rounded-md py-2 pr-9 pl-2.5 text-sm hover:bg-sidebar-accent data-[status=active]:bg-sidebar-accent data-[status=active]:font-medium"
      >
        <span className="line-clamp-1">{title}</span>
      </Link>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Tùy chọn cho hội thoại ${title}`}
              className="absolute top-1/2 right-1 -translate-y-1/2 opacity-0 group-hover/item:opacity-100 focus-visible:opacity-100 data-[popup-open]:opacity-100"
            />
          }
        >
          <EllipsisIcon />
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-44">
          <DropdownMenuItem onClick={() => update.mutate({ id: c.id, pinned: !c.pinned })}>
            {c.pinned ? <PinOffIcon /> : <PinIcon />}
            {c.pinned ? "Bỏ ghim" : "Ghim"}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setRenaming(true)}>
            <PencilIcon /> Đổi tên
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem variant="destructive" onClick={() => setConfirming(true)}>
            <Trash2Icon /> Xóa
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xóa hội thoại?</AlertDialogTitle>
            <AlertDialogDescription>
              “{title}” và mọi câu trả lời trong đó sẽ bị xóa khỏi máy này. Không thể hoàn tác.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Hủy</AlertDialogCancel>
            <AlertDialogAction variant="destructive" disabled={remove.isPending} onClick={deleteConversation}>
              Xóa hội thoại
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}
