// Actions shared by the document list and the document page.
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { useDeleteDocument } from "@/api/client";
import type { DocumentOut } from "@/api/types";
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
import { forgetIdleChats } from "@/features/chat/chats";
import { useUi } from "@/stores/ui";

export const titleOf = (d: DocumentOut) => d.title ?? d.current_version.file_name;

/** Start a new question limited to one document (FR-14). */
export function useAskAbout() {
  const navigate = useNavigate();
  return (documentId: string) => {
    useUi.getState().setScope([documentId]);
    navigate({ to: "/" });
  };
}

interface DeleteProps {
  document: DocumentOut | null;
  onClose: () => void;
  onDeleted?: () => void;
}

/** Confirm, then delete a document with its versions, index and the answers citing it (UC03, BR10). */
export function DeleteDocumentDialog({ document, onClose, onDeleted }: DeleteProps) {
  const remove = useDeleteDocument();
  const confirm = () =>
    document &&
    remove.mutate(document.id, {
      onSuccess: () => {
        useUi.setState((s) => ({ scope: s.scope.filter((id) => id !== document.id) }));
        useUi.getState().closeSource();
        forgetIdleChats();
        onClose();
        onDeleted?.();
        toast.success("Đã xóa tài liệu");
      },
      onError: () => toast.error("Không xóa được tài liệu. Thử lại."),
    });
  return (
    <AlertDialog open={document !== null} onOpenChange={(open) => !open && onClose()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Xóa tài liệu?</AlertDialogTitle>
          <AlertDialogDescription>
            “{document && titleOf(document)}” sẽ bị xóa khỏi máy này cùng mọi phiên bản, chỉ mục, kết quả rà soát và các
            câu trả lời có trích dẫn tài liệu này. Không thể hoàn tác.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Hủy</AlertDialogCancel>
          <AlertDialogAction variant="destructive" disabled={remove.isPending} onClick={confirm}>
            Xóa tài liệu
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
